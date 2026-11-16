import json
from datetime import date
from sqlalchemy import create_engine, text
from src.database.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

def _executar(sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        linhas = [dict(l) for l in conn.execute(text(sql), params or {}).mappings()]
    return json.loads(json.dumps(linhas, default=str))

def _nao_encontrado(tabela: str, produto: str) -> dict:
    validos = [r["produto"] for r in _executar(f"SELECT DISTINCT produto FROM {tabela} ORDER BY produto")]
    return {"erro": f"Produto '{produto}' não encontrado em {tabela}.", "produtos_disponiveis": validos}

def _filtro_produto(produto: str, coluna: str = "produto"):
    p = produto.strip().lower()
    return f"(LOWER({coluna}) = :p OR LOWER({coluna}) LIKE :pl)", {"p": p, "pl": p + " %"}

def _seguro(funcao):
    def interno(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except Exception as e:
            return {"erro": f"Falha na consulta ({funcao.__name__}): {e}"}
    interno.__name__ = funcao.__name__
    interno.__doc__ = funcao.__doc__
    return interno

@_seguro
def consultar_faturamento_por_produtor(nome_produtor: str | None = None):
    sql = "SELECT produtor_nome, SUM(valor_total) AS faturamento_total FROM financeiro"
    params = {}
    if nome_produtor:
        sql += " WHERE LOWER(produtor_nome) LIKE :n"
        params["n"] = f"%{nome_produtor.strip().lower()}%"
    sql += " GROUP BY produtor_nome ORDER BY faturamento_total DESC"
    rows = _executar(sql, params)
    return rows or {"erro": f"Nenhum registro financeiro para o produtor: {nome_produtor}"}

@_seguro
def consultar_estoque_lotes(produto: str | None = None):
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
    sql, params = "SELECT * FROM sazonalidade", {}
    if produto:
        filtro, params = _filtro_produto(produto)
        sql += " WHERE " + filtro
    rows = _executar(sql, params)
    if produto and not rows:
        return _nao_encontrado("sazonalidade", produto)
    return rows

@_seguro
def consultar_produtores(produto: str | None = None, organico_vigente: bool = False):
    sql = ("SELECT DISTINCT p.id AS produtor_id, p.nome_completo, p.municipio, p.status, "
           "p.certificacao_organica, p.validade_certificacao "
           "FROM produtores p JOIN produtor_produtos pp ON pp.produtor_id = p.id")
    condicoes, params = [], {}
    if produto:
        filtro, p = _filtro_produto(produto, "pp.produto")
        condicoes.append(filtro)
        params.update(p)
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