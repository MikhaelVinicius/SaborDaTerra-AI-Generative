"""Ferramentas de busca documental (RAG) para o orquestrador.

Expõe as ferramentas que permitem ao agente consultar os documentos da
cooperativa (certificações, contratos e fichas técnicas) indexados no
ChromaDB. A busca é semântica, feita por embeddings (Gemini).

Atributos:
    TOOLS (list[Callable]): ferramentas disponíveis para o orquestrador.
        Atualmente contém apenas `consultar_documentos`.

Pré-requisitos:
    - Coleção indexada: `python -m src.database.vector_store`
    - Variável `GEMINI_API_KEY` definida no `.env`.
"""
from src.database.vector_store import consultar_documentos

TOOLS = [consultar_documentos]
