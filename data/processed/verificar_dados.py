import pandas as pd

for arq in ["produtores_tratado", "precos_tratados", "financeiro_tratado", "sazonalidade_tratado", "lotes_tratado"]:
    df = pd.read_csv(f"data/processed/{arq}.csv")
    print(f"=== {arq} ===")
    print(df.dtypes)
    print(df.head(3).to_string(), "\n")