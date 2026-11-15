from datetime import datetime
from rapidfuzz import process, fuzz
from .schemas import PedidoTriado, FlagAlerta

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

def aplicar_regras_negocio(
    pedido: PedidoTriado,
    data_referencia: str,
    catalogo_produtos: list[str],
    fn_get_sazonalidade,      # Alterar quando pegar a base de dados
    fn_get_produtores         # Alterar quando pegar a base de dados
) -> PedidoTriado:
    
    if not pedido.comprador.nome:
        pedido.flags.append(FlagAlerta(
            codigo="DADOS_COMPRADOR_AUSENTES",
            detalhe="Nome do comprador não identificado."
        ))

    mes_entrega = MESES_PT[datetime.strptime(data_referencia, "%Y-%m-%d").month]
    if not pedido.prazo.data_estimada:
        pedido.flags.append(FlagAlerta(
            codigo="PRAZO_AMBIGUO",
            detalhe=f"Não foi possível determinar data exata a partir de '{pedido.prazo.texto_original}'."
        ))
    else:
        dt_ref = datetime.strptime(data_referencia, "%Y-%m-%d")
        dt_ent = datetime.strptime(pedido.prazo.data_estimada, "%Y-%m-%d")
        horas_ate_entrega = (dt_ent - dt_ref).total_seconds() / 3600
        mes_entrega = MESES_PT[dt_ent.month]
        if 0 <= horas_ate_entrega <= 48:
            pedido.urgencia = "alta"
            pedido.flags.append(FlagAlerta(
                codigo="URGENTE",
                detalhe=f"Entrega em menos de 48h ({pedido.prazo.data_estimada})."
            ))

    for item in pedido.itens:
        if item.quantidade is None:
            pedido.flags.append(FlagAlerta(
                codigo="QUANTIDADE_AMBIGUA",
                item=item.produto,
                detalhe=f"Quantidade não especificada em '{item.texto_original}'."
            ))

        match = process.extractOne(item.produto, catalogo_produtos, scorer=fuzz.WRatio)
        if not match or match[1] < 75 or item.produto == "DESCONHECIDO":
            pedido.flags.append(FlagAlerta(
                codigo="PRODUTO_NAO_IDENTIFICADO",
                item=item.produto,
                detalhe=f"'{item.texto_original}' não corresponde ao catálogo da cooperativa."
            ))
            continue

        item.produto = match[0]

        em_safra = fn_get_sazonalidade(item.produto, mes_entrega)
        if not em_safra:
            pedido.flags.append(FlagAlerta(
                codigo="FORA_DE_SAFRA",
                item=item.produto,
                detalhe=f"{item.produto} está fora de safra em {mes_entrega}."
            ))

        produtores = fn_get_produtores(item.produto)
        if item.producao == "organico":
            produtores = [p for p in produtores if p.get("organico") is True]
            if not produtores:
                pedido.flags.append(FlagAlerta(
                    codigo="SEM_PRODUTOR_ORGANICO",
                    item=item.produto,
                    detalhe=f"Nenhum produtor certificado para {item.produto} orgânico."
                ))

        capacidade_total = sum(p.get("capacidade", 0) for p in produtores)
        if item.quantidade and capacidade_total > 0 and item.quantidade > capacidade_total:
            pedido.flags.append(FlagAlerta(
                codigo="QTD_ACIMA_CAPACIDADE",
                item=item.produto,
                detalhe=f"Pedido de {item.quantidade} excede capacidade total ({capacidade_total})."
            ))

    codigos = {f.codigo for f in pedido.flags}
    if codigos & {"PRODUTO_NAO_IDENTIFICADO", "FORA_DE_SAFRA", "QTD_ACIMA_CAPACIDADE", "SEM_PRODUTOR_ORGANICO"}:
        pedido.status = "bloqueado"
    elif pedido.flags or pedido.campos_ausentes:
        pedido.status = "revisar"
    else:
        pedido.status = "pronto"

    return pedido