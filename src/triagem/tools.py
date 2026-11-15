import os
import pandas as pd

PROCESSED_DIR = "data/processed"

def consultar_faturamento_por_produtor(nome_produtor: str = None):
    try:
        df = pd.read_csv(os.path.join(PROCESSED_DIR, "financeiro_tratado.csv"))
        if "produtor_nome" not in df.columns or "valor_total" not in df.columns:
            return "Erro: colunas necessárias não encontradas"

        resumo = df.groupby("produtor_nome")["valor_total"].sum().reset_index()

        if nome_produtor:
            filtrado = resumo[resumo["produtor_nome"].str.contains(nome_produtor, case=False, na=False)]
            if filtrado.empty:
                return f"Nenhum registro encontrado para o produtor: {nome_produtor}"
            return filtrado.to_dict(orient="records")

        return resumo.to_dict(orient="records")

    except Exception as e:
        return f"Erro ao processar a consulta financeira: {e}"

def consultar_estoque_lotes(produto: str = None):
    try:
        df = pd.read_csv(os.path.join(PROCESSED_DIR, "lotes_tratado.csv"))
        if "produto" not in df.columns or "quantidade_kg" not in df.columns:
            return "Erro: colunas necessárias não encontradas"

        resumo = df.groupby("produto")["quantidade_kg"].sum().reset_index()

        if produto:
            filtrado = resumo[resumo["produto"].str.contains(produto, case=False, na=False)]
            if filtrado.empty:
                return f"Nenhum lote encontrado para o produto: {produto}"
            return filtrado.to_dict(orient="records")

        return resumo.to_dict(orient="records")
    except Exception as e:
        return f"Erro ao processar a consulta de lotes: {e}"

def consultar_precos(produto: str = None, tipo: str = None):
    try:
        df = pd.read_csv(os.path.join(PROCESSED_DIR, "precos_tratados.csv"))

        if produto:
            df = df[df["produto"].str.contains(produto, case=False, na=False)]
            if df.empty:
                return f"Nenhum preço encontrado para o produto: {produto}"

        if tipo:
            tipo_lower = tipo.lower()
            if "org" in tipo_lower:
                df = df[df["preco_organico"] != "n/d"]
            elif "con" in tipo_lower:
                # Corrigido para 'preco_convencional' (singular)
                df = df[df["preco_convencional"] != "n/d"]

            if df.empty:
                return f"Nenhum preço encontrado para o tipo '{tipo}' do produto especificado."

        return df.to_dict(orient="records")
    except Exception as e:
        return f"Erro ao processar a consulta de preços: {e}"
    
def consultar_sazonalidade(produto: str = None):
    try:
        df = pd.read_csv(os.path.join(PROCESSED_DIR, "sazonalidade_tratado.csv"))
        if produto:
            filtrado = df[df["produto"].str.contains(produto, case=False, na=False)]
            if filtrado.empty:
                return f"Nenhuma informação de sazonalidade encontrada para o produto: {produto}"
            return filtrado.to_dict(orient="records")

        return df.to_dict(orient="records")
    except Exception as e:
        return f"Erro ao processar a consulta de sazonalidade: {e}"

def consultar_pedidos(comprador: str = None, status: str = None):
    try:
        file_path = os.path.join(PROCESSED_DIR, "pedidos.json")
        df = pd.read_json(file_path)

        if comprador:
            if "comprador" in df.columns:
                df = df[df["comprador"].str.contains(comprador, case=False, na=False)]
            else:
                return "Erro: coluna 'comprador' não encontrada nos pedidos."

            if df.empty:
                return f"Nenhum pedido encontrado para o comprador: {comprador}"

        if status:
            if "status" in df.columns:
                df = df[df["status"].str.contains(status, case=False, na=False)]
            else:
                return "Erro: coluna 'status' não encontrada nos pedidos."

            if df.empty:
                return f"Nenhum pedido encontrado com o status: {status}"

        return df.to_dict(orient="records")
    except Exception as e:
        return f"Erro ao processar a consulta de pedidos: {e}"
    
if __name__ == "__main__":
    print("--- Testando Ferramentas para Agente de IA ---")
    print("\n1. Faturamento geral:")
    print(consultar_faturamento_por_produtor())
    
    print("\n2. Estoque de lotes:")
    print(consultar_estoque_lotes())

    print("\n3. Consulta de Preços (com filtro de exemplo para orgânico):")
    print(consultar_precos(tipo="organico"))

    print("\n4. Consulta de Sazonalidade:")
    print(consultar_sazonalidade())

    print("\n5. Consulta de Pedidos:")
    print(consultar_pedidos())