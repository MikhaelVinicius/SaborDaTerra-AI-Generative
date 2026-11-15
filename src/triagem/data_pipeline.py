import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "data", "processed", "raw", "documents", "dados_csv"))
PROCESSED_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "data", "processed"))

os.makedirs(PROCESSED_DIR, exist_ok=True)

def limpar_produtores(df):
    if "nome" in df.columns:
        df["nome"] = df["nome"].astype(str).str.strip().str.title()
    if "cidade" in df.columns:
        df["cidade"] = df["cidade"].astype(str).str.strip().str.title()
    return df

def limpar_preco(df):
    if "preco" in df.columns:
        df["preco"] = (
            df['preco']
            .astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        df["preco"] = pd.to_numeric(df["preco"], errors="coerce")
    return df

def limpar_financeiro(df):
    for col in ["valor", "total", "montante"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("R$", "", regex=False)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    return df

def limpar_sazonalidade(df):
    for col in ["produto", "mes", "estacao"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()
    return df

def limpar_lotes(df):
    for col_id in ["lote_id", "lotes_id"]:
        if col_id in df.columns:
            df[col_id] = df[col_id].astype(str).str.strip().str.upper()

    if "quantidade" in df.columns:
        df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0).astype(int)

    for col in ["data_colheita", "validade"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df

def relatorio_qualidade(nome_base, df):
    valores_nulos = df.isnull().sum().sum()
    print(f"[{nome_base}] Registros: {len(df)} | Valores Nulos Totais: {valores_nulos}")
    if valores_nulos > 0:
        print(df.isnull().sum()[df.isnull().sum() > 0])
    print("-" * 40)


def executar_pipeline():
    try:
        print("--- INICIANDO INGESTÃO ---")
        df_produtores = pd.read_csv(os.path.join(DATA_DIR, 'produtores.csv'))
        print(f"produtores.csv: {len(df_produtores)} registros carregados.")

        df_precos = pd.read_csv(os.path.join(DATA_DIR, "tabela_precos_outubro_2026.csv"))
        print(f"tabela_precos_outubro_2026.csv: {len(df_precos)} registros carregados.")

        df_sazonalidade = pd.read_csv(os.path.join(DATA_DIR, "sazonalidade.csv"))
        print(f"sazonalidade.csv: {len(df_sazonalidade)} registros carregados.")

        df_lotes = pd.read_csv(os.path.join(DATA_DIR, "lotes.csv"))
        print(f"lotes.csv: {len(df_lotes)} registros carregados.")

        df_financeiro = pd.read_csv(os.path.join(DATA_DIR, "financeiro.csv"))
        print(f"financeiro.csv: {len(df_financeiro)} registros carregados.")

        with open(os.path.join(DATA_DIR, "pedidos.json"), "r", encoding="utf-8") as f:
            pedidos_json = json.load(f)
        print(f"pedidos.json: {len(pedidos_json)} pedidos carregados.")

        print("Arquivos carregados com sucesso.\n")

        print("--- INICIANDO LIMPEZA E SANEAMENTO ---")
        df_produtores_limpo = limpar_produtores(df_produtores)
        df_precos_limpo = limpar_preco(df_precos)
        df_financeiro_limpo = limpar_financeiro(df_financeiro)
        df_sazonalidade_limpo = limpar_sazonalidade(df_sazonalidade)
        df_lotes_limpo = limpar_lotes(df_lotes)

        print("\n--- RELATÓRIO DE QUALIDADE (VALORES NULOS) ---")
        relatorio_qualidade("Produtores", df_produtores_limpo)
        relatorio_qualidade("Preços", df_precos_limpo)
        relatorio_qualidade("Financeiro", df_financeiro_limpo)
        relatorio_qualidade("Sazonalidade", df_sazonalidade_limpo)
        relatorio_qualidade("Lotes", df_lotes_limpo)

        df_produtores_limpo.to_csv(os.path.join(PROCESSED_DIR, "produtores_tratado.csv"), index=False)
        df_precos_limpo.to_csv(os.path.join(PROCESSED_DIR, "precos_tratados.csv"), index=False)
        df_financeiro_limpo.to_csv(os.path.join(PROCESSED_DIR, "financeiro_tratado.csv"), index=False)
        df_sazonalidade_limpo.to_csv(os.path.join(PROCESSED_DIR, "sazonalidade_tratado.csv"), index=False)
        df_lotes_limpo.to_csv(os.path.join(PROCESSED_DIR, "lotes_tratado.csv"), index=False)

        
        print("Dados limpos e salvos com sucesso em 'data/processed/'!")
        
        return (df_produtores_limpo, df_precos_limpo, df_sazonalidade_limpo, 
                df_lotes_limpo, df_financeiro_limpo, pedidos_json)

    except Exception as e:
        print(f"\nErro ao ler os arquivos. Verifique se eles estão na pasta '{DATA_DIR}'. Detalhe técnico: {e}")
        return None

if __name__ == "__main__":
    executar_pipeline()