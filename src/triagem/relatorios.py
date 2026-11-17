import os
import pandas as pd

PROCESSED_DIR = "data/processed"

def carregar_dados_processados():
    try:
        produtores = pd.read_csv(os.path.join(PROCESSED_DIR, "produtores_tratado.csv"))
        precos = pd.read_csv(os.path.join(PROCESSED_DIR, "precos_tratados.csv"))
        financeiro = pd.read_csv(os.path.join(PROCESSED_DIR, "financeiro_tratado.csv"))
        sazonalidade = pd.read_csv(os.path.join(PROCESSED_DIR, "sazonalidade_tratado.csv"))
        lotes = pd.read_csv(os.path.join(PROCESSED_DIR, "lotes_tratado.csv"))
        
        print("Dados processados carregados com sucesso para relatórios!\n")
        return produtores, precos, financeiro, sazonalidade, lotes
    except Exception as e:
        print(f"Erro ao carregar os dados processados. Execute o data_pipeline.py primeiro. Detalhe: {e}")
        return None, None, None, None, None

def relatorio_financeiro_por_produtor(df_financeiro):
    print("--- FATURAMENTO TOTAL POR PRODUTOR ---")
    if "produtor_nome" in df_financeiro.columns and "valor_total" in df_financeiro.columns:
        resumo = df_financeiro.groupby("produtor_nome")["valor_total"].sum().reset_index()
        resumo = resumo.sort_values(by="valor_total", ascending=False)
        print(resumo.to_string(index=False))
    else:
        print("Colunas necessárias não encontradas no financeiro.")
    print("-" * 45)

def relatorio_lotes_por_produto(df_lotes):
    print("--- QUANTIDADE TOTAL DE LOTES POR PRODUTO ---")
    if "produto" in df_lotes.columns and "quantidade_kg" in df_lotes.columns:
        resumo = df_lotes.groupby("produto")["quantidade_kg"].sum().reset_index()
        resumo = resumo.sort_values(by="quantidade_kg", ascending=False)
        print(resumo.to_string(index=False))
    else:
        print("Colunas necessárias não encontradas nos lotes.")
    print("-" * 45)

def gerar_todos_relatorios():
    produtores, precos, financeiro, sazonalidade, lotes = carregar_dados_processados()
    
    if financeiro is not None:
        relatorio_financeiro_por_produtor(financeiro)
        
    if lotes is not None:
        relatorio_lotes_por_produto(lotes)

if __name__ == "__main__":
    gerar_todos_relatorios()