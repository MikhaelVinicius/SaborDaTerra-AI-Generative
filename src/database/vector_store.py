import re
import sys
from pathlib import Path

import chromadb
from google import genai
from google.genai import types
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.database.config import (CHROMA_COLLECTION, CHROMA_DIR, DOCUMENTS_DIR,
                                 EMBEDDING_MODEL)

EXTENSOES = {".pdf", ".txt", ".md"}
DIST_MAX = 0.32   
MIN_CHARS = 150   
splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
_cliente = None


def _mascarar(texto: str) -> str:
    texto = re.sub(r"\d{3}\.\d{3}\.\d{3}-\d{2}", "[CPF omitido]", texto)
    texto = re.sub(r"(Ag\.|C/C)[ \t]*[\d\-]+", r"\1 [omitido]", texto)
    texto = re.sub(r"(Chave PIX:)[ \t]*.+", r"\1 [omitido]", texto)
    return texto


def embed(textos: list[str], tarefa: str) -> list[list[float]]:
    global _cliente
    if _cliente is None:
        _cliente = genai.Client()
    vetores = []
    for i in range(0, len(textos), 50):
        resp = _cliente.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=textos[i:i + 50],
            config=types.EmbedContentConfig(task_type=tarefa),
        )
        vetores.extend(e.values for e in resp.embeddings)
    return vetores


def ler_paginas(caminho: Path) -> list[tuple[int, str]]:
    if caminho.suffix.lower() == ".pdf":
        import pdfplumber
        with pdfplumber.open(caminho) as pdf:
            return [(i, (p.extract_text() or "").strip()) for i, p in enumerate(pdf.pages, start=1)]
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        texto = caminho.read_text(encoding="cp1252")
    return [(1, texto.strip())]


def indexar():
    chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        chroma.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    colecao = chroma.create_collection(CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})

    total, sem_texto = 0, []
    for arquivo in sorted(DOCUMENTS_DIR.rglob("*")):
        if arquivo.suffix.lower() not in EXTENSOES:
            continue
        rel = arquivo.relative_to(DOCUMENTS_DIR).as_posix()
        categoria = rel.split("/")[0] 

        ids, trechos, metas = [], [], []
        for pagina, texto in ler_paginas(arquivo):
            if not texto:
                sem_texto.append(f"{rel} p.{pagina}")
                continue
            texto = _mascarar(texto) 
            for n, trecho in enumerate(splitter.split_text(texto)):
                ids.append(f"{rel}|p{pagina}|c{n}")
                trechos.append(trecho)
                metas.append({"fonte": rel, "categoria": categoria, "pagina": pagina})

        if trechos:
            vetores = embed([f"Documento: {m['fonte']}\n{t}" for t, m in zip(trechos, metas)],
                            "RETRIEVAL_DOCUMENT")
            colecao.add(ids=ids, documents=trechos, metadatas=metas, embeddings=vetores)
            total += len(trechos)
            print(f"  {rel}: {len(trechos)} trechos")

    print(f"\nTotal: {total} trechos indexados.")
    if sem_texto:
        print(f"ATENÇÃO: {len(sem_texto)} página(s) sem texto extraível (PDF escaneado? precisa de OCR):")
        print("  " + "\n  ".join(sem_texto))


def buscar(pergunta: str, k: int = 5, categoria: str | None = None) -> list[dict]:
    colecao = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(CHROMA_COLLECTION)
    r = colecao.query(
        query_embeddings=embed([pergunta], "RETRIEVAL_QUERY"),
        n_results=k,
        where={"categoria": categoria} if categoria else None,
    )
    return [
        {"trecho": _mascarar(d), "fonte": m["fonte"], "pagina": m["pagina"], "distancia": round(dist, 4)}
        for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]


def consultar_documentos(pergunta: str, categoria: str | None = None, k: int = 5) -> dict:
    """Busca trechos nos documentos da cooperativa (certificações orgânicas, laudos
    sanitários, inspeção ADAGRO, contratos e fichas técnicas) e retorna os trechos
    com o arquivo de origem. categoria opcional: 'certificacoes', 'contratos' ou
    'fichas_tecnicas'. Use para perguntas sobre o conteúdo de documentos."""
    try:
        itens = buscar(pergunta, k, categoria)
    except Exception as e:
        return {"erro": f"Falha na busca documental: {e}"}

    relevantes = [i for i in itens
                  if i["distancia"] <= DIST_MAX and len(i["trecho"]) >= MIN_CHARS]
    if not relevantes:
        return {"erro": "Nenhum trecho relevante encontrado nos documentos.",
                "instrucao": "Informe ao usuário que não encontrou a informação. Não invente."}

    por_fonte: dict[str, list[str]] = {}
    for i in relevantes:
        por_fonte.setdefault(i["fonte"], []).append(i["trecho"])
    return {"resultados": [{"fonte": f, "trechos": t} for f, t in por_fonte.items()]}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for item in buscar(" ".join(sys.argv[1:])):
            print(f"[{item['fonte']} | p.{item['pagina']} | dist {item['distancia']}]")
            print(item["trecho"][:300], "\n")
    else:
        indexar()