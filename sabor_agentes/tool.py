"""Adaptador público das ferramentas de relatórios e consultas de agentes."""

from sabor_agent.data_tools import (
    get_producer_summary as _get_producer_summary,
    lookup_lot as _lookup_lot,
    lookup_price as _lookup_price,
)


def get_producer_summary(producer_id: str, start_date: str, end_date: str) -> dict:
    """Consulta vendas e pagamentos de um produtor em um período inclusivo.

    Use quando a pessoa pedir um relatório financeiro de produtor. Informe o ID
    do produtor e as datas inicial e final no formato AAAA-MM-DD.
    """
    return _get_producer_summary(producer_id, start_date, end_date)


def lookup_price(product_query: str) -> dict:
    """Consulta os preços de outubro de 2026 para um produto.

    Use quando a pessoa perguntar o preço de um produto. A resposta separa
    correspondências exatas de variantes; não escolha uma variante nem calcule
    descontos.
    """
    return _lookup_price(product_query)


def lookup_lot(lot_id: str) -> dict:
    """Consulta os dados registrados de rastreabilidade de um lote.

    Use quando a pessoa perguntar sobre um lote específico. Retorna somente os
    campos operacionais disponíveis, sem nome ou CPF do produtor. A chave
    ``found`` informa se o lote existe; quando não existe, ``lot`` é None.
    """
    lot = _lookup_lot(lot_id)
    return {"found": lot is not None, "lot_id": lot_id, "lot": lot}


TOOLS = [get_producer_summary, lookup_price, lookup_lot]
