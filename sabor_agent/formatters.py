"""Formata resultados tabulares sem acrescentar conclusões aos dados."""

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


_PAYMENT_LABELS = (
    ("paid", "Pagos"),
    ("pending", "Pendentes"),
    ("unclassified", "Não classificados"),
)


def format_producer_summary(summary: Mapping[str, Any]) -> str:
    """Formata um resumo financeiro mantendo período, totais e fonte retornados."""
    producer_id = _present(summary.get("producer_id"))
    producer_name = _present(summary.get("producer_name"))
    if producer_name:
        title = f"Resumo financeiro de {producer_name}"
        if producer_id:
            title += f" (produtor {producer_id})"
    else:
        title = "Resumo financeiro"
        if producer_id:
            title += f" do produtor {producer_id}"
    lines = [title]

    period = summary.get("period")
    if isinstance(period, Mapping):
        start = _present(period.get("start"))
        end = _present(period.get("end"))
        if start and end:
            lines.append(f"Período: {start} a {end}")

    total_sales = _format_number(summary.get("total_sales"), decimal_places=2)
    if total_sales is not None:
        lines.append(f"Vendas: {total_sales}")

    total_quantity = _format_number(summary.get("total_quantity_kg"))
    if total_quantity is not None:
        lines.append(f"Quantidade registrada: {total_quantity} kg")

    transaction_count = _present(summary.get("transaction_count"))
    if transaction_count is not None:
        lines.append(f"Transações no período: {transaction_count}")

    payments = summary.get("payments")
    payment_lines = []
    if isinstance(payments, Mapping):
        for key, label in _PAYMENT_LABELS:
            payment = payments.get(key)
            if not isinstance(payment, Mapping):
                continue
            amount = _format_number(payment.get("amount"), decimal_places=2)
            count = _present(payment.get("transactions"))
            if amount is not None and count is not None:
                transaction_label = "transação" if str(count) == "1" else "transações"
                payment_lines.append(f"- {label}: {amount} ({count} {transaction_label})")
    if payment_lines:
        lines.append("Pagamentos:")
        lines.extend(payment_lines)

    _append_source(lines, summary.get("source_file"))
    return "\n".join(lines)


def format_price_lookup(result: Mapping[str, Any]) -> str:
    """Formata preços exatos e apresenta variantes separadamente para confirmação."""
    period = _present(result.get("period"))
    title = "Consulta de preços"
    if period:
        title += f" — período: {period}"
    lines = [title]

    matches = _rows(result.get("matches"))
    suggestions = _rows(result.get("suggestions"))
    if matches:
        lines.append("Correspondências exatas:")
        lines.extend(_format_price_row(row) for row in matches)
    elif suggestions:
        lines.append("Nenhuma correspondência exata.")
    else:
        lines.append("Nenhum produto encontrado na tabela consultada.")

    if suggestions:
        lines.append("Variantes para confirmar:")
        lines.extend(_format_price_row(row) for row in suggestions)

    _append_source(lines, result.get("source_file"))
    return "\n".join(lines)


def format_lot_lookup(lot: Mapping[str, Any] | None) -> str:
    """Formata somente os campos presentes no resultado de uma consulta de lote."""
    if lot is None:
        return "Lote não encontrado."

    lot_id = _present(lot.get("lot_id"))
    lines = [f"Lote {lot_id}" if lot_id else "Dados do lote"]
    fields = (
        ("harvest_date", "Data da colheita"),
        ("delivery_date", "Data da entrega"),
        ("producer_id", "ID do produtor"),
        ("product", "Produto"),
        ("quantity_kg", "Quantidade (kg)"),
        ("buyer", "Comprador"),
        ("order_id", "ID do pedido"),
        ("transport_temperature_c", "Temperatura de transporte"),
        ("expiration_date", "Validade"),
        ("visual_inspection", "Inspeção visual"),
        ("notes", "Observações"),
    )
    for key, label in fields:
        value = _present(lot.get(key))
        if value is None:
            continue
        if key == "transport_temperature_c":
            value = _format_temperature(value)
        lines.append(f"{label}: {value}")

    _append_source(lines, lot.get("source_file"))
    return "\n".join(lines)


def format_producer_order_notification(
    producer_name: str,
    allocated_items: Sequence[Mapping[str, Any]],
    *,
    delivery_deadline: str | None = None,
    order_reference: str | None = None,
    confirmation_instruction: str | None = None,
) -> str:
    """Formata um rascunho a partir de itens já alocados a um produtor.

    Esta função não interpreta pedidos, escolhe produtores nem envia mensagens.
    Cada item precisa conter ``product``, ``quantity`` e ``unit``.
    """
    name = _required_notification_value(producer_name, "producer_name")
    if isinstance(allocated_items, (str, bytes)) or not isinstance(
        allocated_items, Sequence
    ):
        raise ValueError("allocated_items deve ser uma sequência de itens já alocados.")
    if not allocated_items:
        raise ValueError("allocated_items deve conter ao menos um item já alocado.")

    item_lines = []
    for index, item in enumerate(allocated_items, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"allocated_items[{index - 1}] deve ser um objeto.")
        product = _required_notification_value(
            item.get("product"), f"allocated_items[{index - 1}].product"
        )
        quantity = _required_notification_value(
            item.get("quantity"), f"allocated_items[{index - 1}].quantity"
        )
        unit = _required_notification_value(
            item.get("unit"), f"allocated_items[{index - 1}].unit"
        )
        item_lines.append(f"- {product} — {quantity} {unit}")

    lines = [
        f"Olá, {name}!",
        "",
        "Há um novo pedido com os seguintes itens destinados a você:",
        *item_lines,
    ]

    optional_lines = (
        ("Prazo de entrega", delivery_deadline),
        ("Referência", order_reference),
    )
    for label, value in optional_lines:
        text = _optional_notification_value(value)
        if text:
            lines.append(f"{label}: {text}")

    instruction = _optional_notification_value(confirmation_instruction)
    if instruction:
        lines.append(instruction)

    return "\n".join(lines)


def _format_price_row(row: Mapping[str, Any]) -> str:
    product = _present(row.get("product"))
    unit = _present(row.get("unit"))
    label = f"{product} ({unit})" if product and unit else product or ""

    details = []
    conventional = _format_number(row.get("conventional_price"), decimal_places=2)
    organic = _format_number(row.get("organic_price"), decimal_places=2)
    if conventional is not None:
        details.append(f"convencional {conventional}")
    if organic is not None:
        details.append(f"orgânico {organic}")

    line = f"- {label}" if label else "-"
    if details:
        line += ": " + "; ".join(details)

    discount = _present(row.get("wholesale_discount_pct"))
    if discount is not None:
        discount_number = _format_number(discount)
        discount_text = f"{discount_number}%" if discount_number is not None else discount
        line += f"; desconto de atacado informado {discount_text}"

    minimum = _format_number(row.get("wholesale_minimum_kg"))
    if minimum is not None:
        line += f"; volume mínimo informado {minimum} kg"

    notes = _present(row.get("notes"))
    if notes is not None:
        line += f"; observação: {notes}"
    return line


def _format_number(value: Any, *, decimal_places: int | None = None) -> str | None:
    text = _present(value)
    if text is None:
        return None
    try:
        number = Decimal(text.replace(",", "."))
    except InvalidOperation:
        return text
    if not number.is_finite():
        return text

    if decimal_places is not None:
        formatted = f"{abs(number):.{decimal_places}f}"
    else:
        formatted = format(abs(number).normalize(), "f")
    integer, separator, fraction = formatted.partition(".")
    grouped_integer = f"{int(integer):,}".replace(",", ".")
    sign = "-" if number.is_signed() else ""
    if separator:
        return f"{sign}{grouped_integer},{fraction}"
    return f"{sign}{grouped_integer}"


def _format_temperature(value: str) -> str:
    try:
        Decimal(value.replace(",", "."))
    except InvalidOperation:
        return value
    return f"{_format_number(value)} °C"


def _present(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _append_source(lines: list[str], value: Any) -> None:
    source = _present(value)
    if source:
        lines.append(f"Fonte: {source}")


def _required_notification_value(value: Any, field_name: str) -> str:
    text = _optional_notification_value(value)
    if text is None:
        raise ValueError(f"{field_name} não pode estar vazio.")
    return text


def _optional_notification_value(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None
