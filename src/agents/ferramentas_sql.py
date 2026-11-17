import json
import functools
from datetime import date
from sqlalchemy import create_engine, text
from src.database.config import DATABASE_URL

engine = create_engine(DATABASE_URL)


def _executar(sql: str, params: dict | None = None) -> list[dict]:
    """Executa uma consulta SQL e devolve as linhas como lista de dicts serializáveis em JSON."""
    with engine.connect() as conn:
        linhas = [dict(l) for l in conn.execute(text(sql), params or {}).mappings()]
    return json.loads(json.dumps(linhas, default=str))


def _nao_encontrado(tabela: str, produto: str) -> dict:
    """Monta o erro padrão de produto inexistente, listando os nomes válidos da tabela
    para o modelo poder corrigir a busca."""
    validos = [r["produto"] for r in _executar(f"SELECT DISTINCT produto FROM {tabela} ORDER BY produto")]
    return {"erro": f"Produto '{produto}' não encontrado em {tabela}.", "produtos_disponiveis": validos}


def _filtro_produto(produto: str, coluna: str = "produto"):
    """Gera o filtro SQL de produto: igualdade exata ou prefixo (ex.: 'goiaba paluma'
    também acha 'goiaba paluma extra'). Retorna (condição, parâmetros)."""
    p = produto.strip().lower()
    return f"(LOWER({coluna}) = :p OR LOWER({coluna}) LIKE :pl)", {"p": p, "pl": p + " %"}


def _seguro(funcao):
    """Decorator: transforma exceções em {'erro': ...} para uma consulta com falha
    não derrubar o chat. Preserva nome e docstring (functools.wraps)."""
    @functools.wraps(funcao)
    def interno(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except Exception as e:
            return {"erro": f"Falha na consulta ({funcao.__name__}): {e}"}
    return interno


@_seguro
def consultar_faturamento_por_produtor(nome_produtor: str | None = None):
    """Consulta o faturamento financeiro dos produtores no banco de dados.

    Use para perguntas sobre quanto um produtor vendeu, recebeu ou tem a receber,
    ou para comparar o faturamento entre produtores.

    Args:
        nome_produtor: nome (ou parte do nome) do produtor, sem diferenciar
            maiúsculas. Se omitido, devolve todos os produtores.

    Returns:
        Lista ordenada do maior para o menor faturamento, com produtor_nome,
        faturamento_total, recebido (pago) e pendente. Se nada for encontrado,
        devolve {'erro': ...}.
    """
    sql = (
        "SELECT produtor_nome, "
        "SUM(valor_total) AS faturamento_total, "
        "SUM(CASE WHEN status_pagamento = 'pago' THEN valor_total ELSE 0 END) AS recebido, "
        "SUM(CASE WHEN status_pagamento = 'pendente' THEN valor_total ELSE 0 END) AS pendente "
        "FROM financeiro"
    )
    params = {}
    if nome_produtor:
        sql += " WHERE LOWER(produtor_nome) LIKE :n"
        params["n"] = f"%{nome_produtor.strip().lower()}%"
    sql += " GROUP BY produtor_nome ORDER BY faturamento_total DESC"
    rows = _executar(sql, params)
    return rows or {"erro": f"Nenhum registro financeiro para o produtor: {nome_produtor}"}


@_seguro
def consultar_estoque_lotes(produto: str | None = None):
    """Totaliza, por produto, a quantidade em kg dos lotes registrados.

    Use para perguntas como "quanto temos de mel?" ou "quais produtos têm lotes
    registrados?". Para os detalhes de UM lote específico (comprador, validade,
    inspeção), use consultar_lote.

    Args:
        produto: nome do produto (ex.: 'mel silvestre'); aceita prefixo. Se
            omitido, devolve todos os produtos.

    Returns:
        Lista com produto, quantidade_kg_total e n_lotes, em ordem alfabética.
        Se o produto não existir, devolve {'erro': ..., 'produtos_disponiveis': [...]}.
    """
    sql = "SELECT produto, SUM(quantidade_kg) AS quantidade_kg_total, COUNT(*) AS n_lotes FROM lotes"
    params = {}
    if produto:
        filtro, params = _filtro_produto(produto)
        sql += " WHERE " + filtro
    sql += " GROUP BY produto ORDER BY produto"
    rows = _executar(sql, params)
    if produto and not rows:
        return _nao_encontrado("lotes", produto)
    return rows


@_seguro
def consultar_lote(lote_id: str):
    """Busca os detalhes de um lote específico pelo código (rastreabilidade).

    Use quando a pergunta citar um código de lote, como 'LOT-2026-0089'. Para
    totais por produto, use consultar_estoque_lotes.

    Args:
        lote_id: código do lote, sem diferenciar maiúsculas.

    Returns:
        Lista com o lote: datas de colheita e entrega, produtor, produto,
        quantidade_kg, comprador, pedido, temperatura de transporte, validade,
        inspeção visual e observação. Se o código não existir, devolve
        {'erro': ..., 'lotes_cadastrados': [...]}.
    """
    rows = _executar(
        "SELECT lote_id, data_colheita, data_entrega, produtor_id, produtor_nome, produto, quantidade_kg, "
        "comprador, pedido_id, temperatura_transporte_c, validade, inspecao_visual, observacao "
        "FROM lotes WHERE UPPER(lote_id) = :l", {"l": lote_id.strip().upper()})
    if rows:
        return rows
    existentes = [r["lote_id"] for r in _executar("SELECT lote_id FROM lotes ORDER BY lote_id")]
    return {"erro": f"Lote '{lote_id}' não encontrado.", "lotes_cadastrados": existentes}


@_seguro
def consultar_precos(produto: str | None = None, tipo: str | None = None):
    """Consulta a tabela de preços da cooperativa (por kg ou unidade).

    Use para perguntas sobre preço de um produto, diferença entre orgânico e
    convencional, e desconto de atacado. Para preços de contratos específicos
    (ex.: PNAE), use consultar_documentos.

    Args:
        produto: nome do produto (ex.: 'queijo coalho'); aceita prefixo, então
            'goiaba paluma' traz também as variações (especial, extra). Se
            omitido, devolve a tabela inteira.
        tipo: 'organico' ou 'convencional', para só trazer produtos que têm
            esse tipo de preço.

    Returns:
        Lista com produto, unidade, preco_convencional, preco_organico,
        desconto_atacado_pct, volume_minimo_atacado_kg e observacao. Se o
        produto não existir, devolve {'erro': ..., 'produtos_disponiveis': [...]}.
    """
    condicoes, params = [], {}
    if produto:
        filtro, p = _filtro_produto(produto)
        condicoes.append(filtro)
        params.update(p)
    if tipo:
        t = tipo.lower()
        if "org" in t:
            condicoes.append("preco_organico IS NOT NULL")
        elif "con" in t:
            condicoes.append("preco_convencional IS NOT NULL")
    sql = "SELECT * FROM precos" + (" WHERE " + " AND ".join(condicoes) if condicoes else "")
    rows = _executar(sql, params)
    if produto and not rows:
        return _nao_encontrado("precos", produto)
    return rows or {"erro": f"Nenhum preço encontrado para o tipo '{tipo}'."}


@_seguro
def consultar_sazonalidade(produto: str | None = None):
    """Consulta a disponibilidade mensal (safra) dos produtos.

    Use para perguntas como "quando tem manga?" ou "o que está na safra em
    dezembro?". SEMPRE informe o produto quando a pergunta for sobre um item
    específico: sem filtro a consulta devolve todos os produtos (muitos dados).

    Args:
        produto: nome do produto (ex.: 'manga tommy'); aceita prefixo.

    Returns:
        Lista com, para cada produto, a disponibilidade em cada mês (jan a dez:
        'alta', 'media', 'baixa' ou 'nenhuma') e uma observação sobre a safra.
        Se o produto não existir, devolve {'erro': ..., 'produtos_disponiveis': [...]}.
    """
    sql, params = "SELECT * FROM sazonalidade", {}
    if produto:
        filtro, params = _filtro_produto(produto)
        sql += " WHERE " + filtro
    rows = _executar(sql, params)
    if produto and not rows:
        return _nao_encontrado("sazonalidade", produto)
    return rows


@_seguro
def consultar_produtores(produto: str | None = None, organico_vigente: bool = False,
                         nome: str | None = None):
    """Lista produtores por produto, certificação orgânica vigente ou nome.
    Use para listas de produtores e para descobrir o ID (produtor_id) a partir do nome.

    Args:
        produto: filtra produtores que fornecem esse produto (ex.: 'mel').
        organico_vigente: se True, só produtores com certificação orgânica cuja
            validade ainda não venceu hoje. Certificados vencidos ficam de fora.
        nome: nome (ou parte do nome) do produtor.

    Returns:
        Lista com produtor_id, nome_completo, municipio, status,
        certificacao_organica e validade_certificacao. Atenção: o campo
        certificacao_organica pode dizer 'sim' mesmo com a validade vencida;
        para saber se está vigente, use organico_vigente=True. Detalhes do
        certificado (número, produtos certificados) estão em consultar_documentos.
    """
    sql = ("SELECT DISTINCT p.id AS produtor_id, p.nome_completo, p.municipio, p.status, "
           "p.certificacao_organica, p.validade_certificacao "
           "FROM produtores p JOIN produtor_produtos pp ON pp.produtor_id = p.id")
    condicoes, params = [], {}
    if produto:
        filtro, p = _filtro_produto(produto, "pp.produto")
        condicoes.append(filtro)
        params.update(p)
    if nome:
        condicoes.append("LOWER(p.nome_completo) LIKE :nome")
        params["nome"] = f"%{nome.strip().lower()}%"
    if organico_vigente:
        condicoes.append("p.certificacao_organica = 'sim' AND p.validade_certificacao >= :hoje")
        params["hoje"] = date.today().isoformat()
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    rows = _executar(sql + " ORDER BY p.nome_completo", params)
    if produto and not rows:
        return _nao_encontrado("produtor_produtos", produto)
    return rows or {"erro": "Nenhum produtor encontrado com esses filtros."}


@_seguro
def consultar_pedidos(comprador: str | None = None, status: str | None = None):
    """Consulta os pedidos que passaram pela triagem automática.

    Use para perguntas sobre pedidos de um comprador, ou sobre pedidos com
    determinado status, urgência ou alertas.

    Args:
        comprador: nome (ou parte do nome) do comprador.
        status: status do pedido, igual ao texto cadastrado (sem diferenciar
            maiúsculas).

    Returns:
        Lista de pedidos com comprador, produto, quantidade, unidade, prazo,
        urgência, status e alertas. Se não houver nenhum, devolve {'erro': ...}.
    """
    condicoes, params = [], {}
    if comprador:
        condicoes.append("LOWER(comprador) LIKE :c")
        params["c"] = f"%{comprador.strip().lower()}%"
    if status:
        condicoes.append("LOWER(status) = :s")
        params["s"] = status.strip().lower()
    sql = "SELECT * FROM pedidos_triados" + (" WHERE " + " AND ".join(condicoes) if condicoes else "")
    return _executar(sql, params) or {"erro": "Nenhum pedido triado encontrado com esses filtros."}


if __name__ == "__main__":
    print(consultar_faturamento_por_produtor())
    print(consultar_estoque_lotes("mel"))
    print(consultar_precos(tipo="organico"))
    print(consultar_sazonalidade("goiaba"))
    print(consultar_produtores("mel", organico_vigente=True))
    print(consultar_pedidos())