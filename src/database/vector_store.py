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
DIST_MAX = 0.32   # distância de cosseno máxima para um trecho ser considerado relevante
MIN_CHARS = 150   # trechos menores (ex.: só rodapé/assinatura) são descartados
splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
_cliente = None


def _mascarar(texto: str) -> str:
    """Oculta dados sensíveis antes de indexar e antes de devolver trechos.

    Mascara CPF, agência e conta bancária (aceitando pontos e hífens nos
    números, ex.: 12345.678-9) e a chave PIX. Não altera CNPJ de empresas.
    """
    texto = re.sub(r"\d{3}\.\d{3}\.\d{3}-\d{2}", "[CPF omitido]", texto)
    texto = re.sub(r"(Ag\.|C/C)[ \t]*\d[\d.\-]*", r"\1 [omitido]", texto)
    texto = re.sub(r"(Chave PIX:)[ \t]*.+", r"\1 [omitido]", texto)
    return texto


def embed(textos: list[str], tarefa: str) -> list[list[float]]:
    """Gera embeddings com o modelo Gemini, em lotes de 50 textos.

    Args:
        textos: textos a vetorizar.
        tarefa: tipo de tarefa do embedding: 'RETRIEVAL_DOCUMENT' para
            indexar trechos ou 'RETRIEVAL_QUERY' para perguntas.

    Returns:
        Lista de vetores, na mesma ordem dos textos.
    """
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
    """Lê um documento e devolve uma lista de (número da página, texto).

    PDFs são lidos página a página (pdfplumber); .txt e .md contam como
    página 1. Páginas sem texto extraível (PDF escaneado) voltam com texto
    vazio e precisariam de OCR.
    """
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
    """Recria a coleção do ChromaDB a partir dos documentos da cooperativa.

    Apaga a coleção existente, lê todos os .pdf/.txt/.md de DOCUMENTS_DIR,
    mascara dados sensíveis, divide em trechos (1200 caracteres, 200 de
    sobreposição), gera embeddings (usa a API do Gemini) e grava com os
    metadados fonte, categoria (primeira pasta) e página. Rode de novo
    sempre que os documentos ou a regra de mascaramento mudarem.
    """
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
    """Busca semântica bruta no ChromaDB, sem filtro de relevância.

    Args:
        pergunta: texto da consulta.
        k: quantidade de trechos a retornar.
        categoria: restringe a 'certificacoes', 'contratos' ou 'fichas_tecnicas'.

    Returns:
        Lista de dicts com trecho (mascarado), fonte, pagina e distancia
        (menor = mais parecido). Para uso do agente, prefira
        consultar_documentos, que aplica o limiar de relevância.
    """
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
    """Busca trechos nos documentos da cooperativa e devolve o texto com o arquivo de origem.

    Use para perguntas sobre o CONTEÚDO de documentos: certificados orgânicos
    (número, validade, produtos certificados, renovação), laudos sanitários,
    inspeção ADAGRO, contratos (prazo de pagamento, vigência, itens e preços
    contratados, penalidades) e fichas técnicas dos produtos. Para dados
    cadastrais, preços da tabela, lotes ou faturamento, use as ferramentas
    consultar_*, que leem o banco.

    Dicas: faça perguntas específicas e cite o nome do produtor, do comprador
    ou do produto; os resultados podem incluir trechos de outros documentos
    parecidos, então confira a fonte de cada trecho antes de responder.

    Args:
        pergunta: pergunta em linguagem natural.
        categoria: opcional, restringe a busca a 'certificacoes', 'contratos'
            ou 'fichas_tecnicas'.
        k: quantos trechos candidatos buscar (padrão 5).

    Returns:
        {'resultados': [{'fonte': arquivo, 'trechos': [texto, ...]}, ...]}
        com os trechos relevantes agrupados por arquivo. Se nada for
        relevante, devolve {'erro': ..., 'instrucao': ...}: nesse caso
        informe ao usuário que não encontrou e não invente. Cite sempre o
        arquivo de origem.
    """
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