import json
import pandas as pd
from sqlalchemy import (Column, DateTime, Float, Integer, MetaData, String,
                        Table, Text, create_engine, func, inspect)
from src.database.config import DATABASE_URL, PROCESSED_DIR

TABELAS = {
    "produtores": "produtores_tratado.csv",
    "precos": "precos_tratados.csv",
    "financeiro": "financeiro_tratado.csv",
    "sazonalidade": "sazonalidade_tratado.csv",
    "lotes": "lotes_tratado.csv",
}

metadata = MetaData()
pedidos_triados = Table(
    "pedidos_triados", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("pedido_origem_id", Integer),
    Column("comprador", String(200)),
    Column("produto", String(100)),
    Column("quantidade", Float),
    Column("unidade", String(20)),
    Column("prazo", String(50)),
    Column("urgencia", String(20)),
    Column("status", String(30)),
    Column("alertas", Text),
    Column("criado_em", DateTime, server_default=func.now()),
)


def _converter_datas(df):
    """CSV não guarda tipos: reconverte colunas de data para datetime."""
    for col in df.columns:
        if col.startswith("data") or "validade" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def carregar():
    engine = create_engine(DATABASE_URL)
    print(f"Banco: {engine.url.render_as_string(hide_password=True)}\n")

    with engine.begin() as conn:
        for tabela, arquivo in TABELAS.items():
            df = _converter_datas(pd.read_csv(PROCESSED_DIR / arquivo))
            df.to_sql(tabela, conn, if_exists="replace", index=False)
            print(f"  {tabela}: {len(df)} linhas")

        prod = pd.read_csv(PROCESSED_DIR / TABELAS["produtores"])
        rel = prod.assign(produto=prod["produtos"].str.split(",")).explode("produto")
        rel = rel[["id", "produto"]].rename(columns={"id": "produtor_id"})
        rel["produto"] = rel["produto"].str.strip().str.lower()
        rel.to_sql("produtor_produtos", conn, if_exists="replace", index=False)
        print(f"  produtor_produtos: {len(rel)} linhas")

        with open(PROCESSED_DIR / "pedidos.json", encoding="utf-8") as f:
            pedidos = json.load(f)
        brutos = pd.DataFrame({"conteudo": [json.dumps(p, ensure_ascii=False) for p in pedidos]})
        brutos.insert(0, "id", range(1, len(brutos) + 1))
        brutos.to_sql("pedidos_brutos", conn, if_exists="replace", index=False)
        print(f"  pedidos_brutos: {len(brutos)} linhas")

        metadata.create_all(conn)

    print("\nTabelas no banco:", sorted(inspect(engine).get_table_names()))


if __name__ == "__main__":
    carregar()