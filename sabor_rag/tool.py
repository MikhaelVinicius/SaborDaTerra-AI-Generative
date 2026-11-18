"""Ferramentas de busca documental (RAG) para o orquestrador.

Este módulo expõe a ferramenta pública de consulta à base documental da
Cooperativa Sabor da Terra. A ferramenta realiza recuperação semântica
sobre documentos indexados no ChromaDB e devolve trechos e fontes para
que o orquestrador produza a resposta final.

A geração da resposta final é responsabilidade do orquestrador central.
"""

from sabor_rag.retriever import retrieve


ALLOWED_CATEGORIES = {
    "certificacoes",
    "contratos",
    "fichas_tecnicas",
}


def consultar_documentos(
    pergunta: str,
    categoria: str | None = None,
    k: int = 5,
) -> dict:
    """
    Consulte esta ferramenta quando precisar buscar informações documentais
    da Cooperativa Sabor da Terra.

    Use para perguntas sobre certificações, inspeções, laudos, contratos,
    fichas técnicas e outras informações presentes na base documental.

    Não use para pedidos, preços, lotes, dados financeiros ou informações
    operacionais estruturadas; nesses casos, utilize as ferramentas de dados.

    Args:
        pergunta: Pergunta ou informação que deve ser pesquisada.
        categoria: Categoria documental opcional. Valores aceitos:
            "certificacoes", "contratos" ou "fichas_tecnicas".
        k: Quantidade máxima de trechos recuperados.

    Returns:
        Dicionário com os documentos e trechos encontrados, incluindo fonte,
        identificador do documento, chunk, categoria e score de similaridade.
    """
    if not pergunta or not pergunta.strip():
        return {
            "erro": "Pergunta inválida.",
            "resultados": [],
        }

    if categoria and categoria not in ALLOWED_CATEGORIES:
        return {
            "erro": f"Categoria documental inválida: {categoria}",
            "resultados": [],
        }

    if k < 1:
        return {
            "erro": "O parâmetro k deve ser maior ou igual a 1.",
            "resultados": [],
        }

    try:
        hits = retrieve(
            pergunta.strip(),
            top_k=k,
            categoria=categoria,
        )
    except Exception as exc:
        return {
            "erro": f"Falha ao consultar a base documental: {exc}",
            "resultados": [],
        }

    if not hits:
        return {
            "erro": (
                "Nenhum trecho documental relevante foi encontrado. "
                "Não invente uma resposta."
            ),
            "resultados": [],
        }

    documentos: dict[str, list[dict]] = {}

    for hit in hits:
        fonte = hit.chunk.source_path

        trecho = {
            "texto": hit.chunk.text,
            "documento": hit.chunk.document_id,
            "chunk_id": hit.chunk.chunk_id,
            "categoria": hit.chunk.category,
            "score": round(hit.score, 4),
        }

        documentos.setdefault(fonte, []).append(trecho)

    resultados = [
        {
            "fonte": fonte,
            "trechos": trechos,
        }
        for fonte, trechos in documentos.items()
    ]

    return {
        "resultados": resultados,
    }


TOOLS = [consultar_documentos]
