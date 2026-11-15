import os
import pandas as pd
from datetime import datetime
from rapidfuzz import process, fuzz
from .schemas import PedidoTriado, FlagAlerta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DIR = os.path.abspath(os.path.join(
    BASE_DIR, "..", "..", "data", "processed"))

MESES_PT = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr",
    5: "mai", 6: "jun", 7: "jul", 8: "ago",
    9: "set", 10: "out", 11: "nov", 12: "dez"
}


def carregar_bases():
    df_produtores = pd.read_csv(os.path.join(
        PROCESSED_DIR, "produtores_tratado.csv"))
    df_sazonalidade = pd.read_csv(os.path.join(
        PROCESSED_DIR, "sazonalidade_tratado.csv"))
    df_produtores_ativos = df_produtores[df_produtores["status"].str.lower(
    ) == "ativo"].copy()
    return df_produtores_ativos, df_sazonalidade


def consultar_sazonalidade(produto: str, mes_col: str, df_sazonalidade: pd.DataFrame) -> tuple[str, str]:
    produtos_saz = df_sazonalidade["produto"].dropna().tolist()
    match = process.extractOne(
        produto.lower(), produtos_saz, scorer=fuzz.WRatio)
    if not match or match[1] < 75:
        return "desconhecido", ""
    linha = df_sazonalidade[df_sazonalidade["produto"] == match[0]].iloc[0]
    nivel = str(linha[mes_col]).strip().lower()
    obs = str(linha["observacao"]) if pd.notna(linha["observacao"]) else ""
    return nivel, obs


def consultar_produtores(produto: str, df_produtores: pd.DataFrame) -> list[dict]:
    encontrados = []
    for _, row in df_produtores.iterrows():
        lista_prod = [p.strip().lower()
                      for p in str(row["produtos"]).split(",")]
        match = process.extractOne(
            produto.lower(), lista_prod, scorer=fuzz.WRatio)
        if match and match[1] >= 75:
            encontrados.append({
                "id": row["id"],
                "nome": row["nome_completo"],
                "organico": str(row["certificacao_organica"]).strip().lower() == "sim"
            })
    return encontrados


def aplicar_regras_negocio(
    pedido: PedidoTriado,
    data_referencia: str,
    catalogo_produtos: list[str]
) -> PedidoTriado:
    df_produtores, df_sazonalidade = carregar_bases()
    pedido.flags = []

    if not pedido.comprador.nome:
        pedido.flags.append(FlagAlerta(
            codigo="DADOS_COMPRADOR_AUSENTES",
            detalhe="Nome do comprador não identificado."
        ))

    mes_entrega = MESES_PT[datetime.strptime(
        data_referencia[:10], "%Y-%m-%d").month]
    if not pedido.prazo.data_estimada:
        pedido.flags.append(FlagAlerta(
            codigo="PRAZO_AMBIGUO",
            detalhe=f"Não foi possível determinar data exata a partir de '{pedido.prazo.texto_original}'."
        ))
    else:
        dt_ref = datetime.strptime(data_referencia[:10], "%Y-%m-%d")
        dt_ent = datetime.strptime(pedido.prazo.data_estimada[:10], "%Y-%m-%d")
        horas_ate_entrega = (dt_ent - dt_ref).total_seconds() / 3600
        mes_entrega = MESES_PT[dt_ent.month]
        if 0 <= horas_ate_entrega <= 48:
            pedido.urgencia = "alta"
            pedido.flags.append(FlagAlerta(
                codigo="URGENTE",
                detalhe=f"Entrega em menos de 48h ({pedido.prazo.data_estimada})."
            ))

    if not pedido.itens:
        pedido.flags.append(FlagAlerta(
            codigo="SEM_ITENS_IDENTIFICADOS",
            detalhe="Nenhum item de compra identificado na mensagem (pode ser consulta, oferta de produtor ou notificação)."
        ))

    for item in pedido.itens:
        if item.quantidade is None:
            pedido.flags.append(FlagAlerta(
                codigo="QUANTIDADE_AMBIGUA",
                item=item.produto,
                detalhe=f"Quantidade não especificada em '{item.texto_original}'."
            ))

        match = process.extractOne(
            item.produto, catalogo_produtos, scorer=fuzz.WRatio)
        if not match or match[1] < 75 or item.produto == "DESCONHECIDO":
            pedido.flags.append(FlagAlerta(
                codigo="PRODUTO_NAO_IDENTIFICADO",
                item=item.produto,
                detalhe=f"'{item.texto_original}' não corresponde ao catálogo da cooperativa."
            ))
            continue

        item.produto = match[0]

        nivel_safra, obs_safra = consultar_sazonalidade(
            item.produto, mes_entrega, df_sazonalidade)
        if nivel_safra == "nenhuma":
            pedido.flags.append(FlagAlerta(
                codigo="FORA_DE_SAFRA",
                item=item.produto,
                detalhe=f"{item.produto} está fora de safra em {mes_entrega}. {obs_safra}".strip(
                )
            ))

        elif nivel_safra == "baixa":
            pedido.flags.append(FlagAlerta(
                codigo="SAFRA_BAIXA",
                item=item.produto,
                detalhe=f"{item.produto} está com disponibilidade baixa em {mes_entrega}. {obs_safra}".strip()
            ))

        produtores = consultar_produtores(item.produto, df_produtores)
        if not produtores:
            pedido.flags.append(FlagAlerta(
                codigo="SEM_PRODUTOR_ATIVO",
                item=item.produto,
                detalhe=f"Nenhum produtor ativo encontrado para {item.produto}."
            ))

        elif item.producao == "organico":
            produtores_org = [p for p in produtores if p["organico"] is True]
            if not produtores_org:
                pedido.flags.append(FlagAlerta(
                    codigo="SEM_PRODUTOR_ORGANICO",
                    item=item.produto,
                    detalhe=f"Nenhum produtor certificado para {item.produto} orgânico."
                ))

    codigos = {f.codigo for f in pedido.flags}
    if codigos & {"PRODUTO_NAO_IDENTIFICADO", "FORA_DE_SAFRA", "SEM_PRODUTOR_ATIVO", "SEM_PRODUTOR_ORGANICO"}:
        pedido.status = "bloqueado"
    elif pedido.flags or pedido.campos_ausentes or pedido.perguntas_de_esclarecimento:
        pedido.status = "revisar"
    else:
        pedido.status = "pronto"

    return pedido
