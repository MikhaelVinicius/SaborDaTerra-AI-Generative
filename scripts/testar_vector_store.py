import statistics
import chromadb

from src.database.config import CHROMA_COLLECTION, CHROMA_DIR, DOCUMENTS_DIR
from src.database.vector_store import EXTENSOES, buscar

POSITIVOS = [
    ("quais produtores têm certificação orgânica para mel?", "cert_organica"),
    ("qual a validade da certificação orgânica da Maria Silva?", "maria_silva_p001"),
    ("certificação orgânica do José Santos", "jose_santos_p002"),
    ("laudo sanitário da queijaria do Cícero", "queijaria_cicero"),
    ("laudo sanitário do apiário", "apiario_jose"),
    ("resultado da inspeção da ADAGRO em 2026", "inspecao_adagro"),
    ("qual o prazo de pagamento no contrato do PNAE?", "contrato_pnae"),
    ("condições de entrega do contrato com o Mercado Bom Preço", "mercado_bom_preco"),
    ("cláusulas do contrato com o Restaurante Raízes", "restaurante_raizes"),
    ("temperatura de conservação do queijo coalho", "queijo_coalho"),
    ("prazo de validade do mel", "mel_silvestre"),
    ("como armazenar goiaba?", "goiaba_paluma"),
]

NEGATIVOS = [
    "qual o preço do bitcoin hoje?",
    "como fazer bolo de chocolate?",
    "quem ganhou a copa do mundo de 2022?",
    "qual a capital da França?",
    "como configurar um roteador wifi?",
]

K = 5


def teste_cobertura():
    print("=== 1. COBERTURA ===")
    col = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(CHROMA_COLLECTION)
    indexados = {m["fonte"] for m in col.get(include=["metadatas"])["metadatas"]}
    em_disco = {a.relative_to(DOCUMENTS_DIR).as_posix()
                for a in DOCUMENTS_DIR.rglob("*") if a.is_file()}
    suportados = {f for f in em_disco if "." + f.rsplit(".", 1)[-1].lower() in EXTENSOES}
    print(f"Chunks: {col.count()} | Arquivos indexados: {len(indexados)}/{len(suportados)}")
    if em_disco - suportados:
        print("Ignorados:", *sorted(em_disco - suportados), sep="\n  ")
    if suportados - indexados:
        print("Sem chunks:", *sorted(suportados - indexados), sep="\n  ")
    print()


def teste_recuperacao():
    print("=== 2. RECUPERAÇÃO ===")
    top1 = topk = 0
    dists = []
    for pergunta, esperado in POSITIVOS:
        res = buscar(pergunta, k=K)
        fontes = [r["fonte"].lower() for r in res]
        ok1 = esperado in fontes[0]
        okk = any(esperado in f for f in fontes)
        top1 += ok1
        topk += okk
        dists.append(res[0]["distancia"])
        marca = "OK   " if ok1 else ("~topk" if okk else "FALHA")
        print(f"[{marca}] d={res[0]['distancia']:.3f} | {pergunta}")
        if not ok1:
            print(f"         top-{K}: {fontes}")
    n = len(POSITIVOS)
    print(f"\nTop-1: {top1}/{n} | Top-{K}: {topk}/{n}")
    print(f"Distância top-1 (positivos): min={min(dists):.3f} "
          f"média={statistics.mean(dists):.3f} max={max(dists):.3f}\n")
    return dists


def teste_negativos(dists_pos):
    print("=== 3. PERGUNTAS SEM RESPOSTA ===")
    dists = []
    for pergunta in NEGATIVOS:
        r = buscar(pergunta, k=1)[0]
        dists.append(r["distancia"])
        print(f"d={r['distancia']:.3f} | {pergunta} -> {r['fonte']}")
    pior_pos, melhor_neg = max(dists_pos), min(dists)
    print(f"\nPior positivo: {pior_pos:.3f} | Melhor negativo: {melhor_neg:.3f}")
    if pior_pos < melhor_neg:
        print(f"Há separação. DIST_MAX sugerido ≈ {(pior_pos + melhor_neg) / 2:.2f}")
    else:
        print("Sem separação clara: as distâncias se sobrepõem. "
              "Dependa mais do prompt do agente do que do limiar.")


if __name__ == "__main__":
    teste_cobertura()
    d = teste_recuperacao()
    teste_negativos(d)