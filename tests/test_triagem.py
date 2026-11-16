import time
import os
import json
from src.triagem.pipeline import triar_pedido

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PEDIDOS_JSON_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "data", "processed", "raw",
                 "documents", "dados_csv", "pedidos.json")
)

CENARIOS_VALIDACAO = [
    {
        "id": "TESTE-PRONTO",
        "data_ref": "2026-11-15",
        "texto": "Bom dia! Aqui é Marcos do Mercado Bom Preço. Preciso de 50 kg de queijo coalho e 30 kg de goiaba paluma para o dia 20/11.",
        "status_esperado": "pronto"
    },
    {
        "id": "TESTE-REVISAR",
        "data_ref": "2026-11-15",
        "texto": "Oi, aqui é Carla do Restaurante Raízes. Manda umas caixas de macaxeira e um pouco de coentro pra semana que vem.",
        "status_esperado": "revisar"
    },
    {
        "id": "TESTE-BLOQUEADO-SAFRA",
        "data_ref": "2026-11-15",
        "texto": "Olá, sou Ana da Escola Municipal. Preciso de 20 kg de umbu e 15 kg de feijão para entrega dia 22/11.",
        "status_esperado": "bloqueado"
    },
    {
        "id": "TESTE-BLOQUEADO-ORGANICO",
        "data_ref": "2026-11-15",
        "texto": "Solicito 10 kg de frango caipira orgânico certificado para o PNAE no dia 25/11.",
        "status_esperado": "bloqueado"
    }
]


def rodar_cenarios_sinteticos():
    print("=" * 60)
    print("1. VALIDANDO CENÁRIOS DE REGRA DE NEGÓCIO (SINTÉTICOS)")
    print("=" * 60)

    for cenario in CENARIOS_VALIDACAO:
        resultado = triar_pedido(
            texto=cenario["texto"],
            data_referencia=cenario["data_ref"],
            pedido_id=cenario["id"]
        )
        status_obtido = resultado["status"]
        passou = "OK" if status_obtido == cenario["status_esperado"] else "FALHOU"

        print(
            f"[{passou}] {cenario['id']} | Esperado: {cenario['status_esperado']} | Obtido: {status_obtido}")
        for flag in resultado["flags"]:
            print(f"   -> Flag [{flag['codigo']}]: {flag['detalhe']}")
        if status_obtido != cenario["status_esperado"]:
            print("   JSON completo para debug:")
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
        print("-" * 60)
        time.sleep(13)


def rodar_pedidos_json(limite: int = 15):
    print("\n" + "=" * 60)
    print("2. RODANDO NOS PEDIDOS REAIS (pedidos.json)")
    print("=" * 60)

    if not os.path.exists(PEDIDOS_JSON_PATH):
        print(f"Arquivo não encontrado em: {PEDIDOS_JSON_PATH}")
        return

    with open(PEDIDOS_JSON_PATH, "r", encoding="utf-8") as f:
        pedidos = json.load(f)[:limite]

    print(f"Total de pedidos carregados: {len(pedidos)}\n")

    for pedido in pedidos:
        pid = pedido["id"]
        data_ref = pedido["data_recebimento"][:10]
        comprador_meta = pedido.get("comprador", "")
        canal_meta = pedido.get("canal", "")
        remetente_meta = pedido.get("remetente", "")

        texto_completo = (
            f"[Canal: {canal_meta} | Remetente: {remetente_meta} | Comprador: {comprador_meta}]\n"
            f"{pedido['mensagem_original']}"
        )

        resultado = triar_pedido(texto=texto_completo,
                                 data_referencia=data_ref, pedido_id=pid)
        itens_nomes = [
            f"{it['produto']} ({it['quantidade']} {it['unidade']})" for it in resultado["itens"]]
        print(
            f"Pedido {pid} ({comprador_meta}) -> Status: {resultado['status'].upper()} | Itens: {itens_nomes} | Flags: {len(resultado['flags'])}")
        for flag in resultado["flags"]:
            print(f"   * [{flag['codigo']}] {flag['detalhe']}")
        if resultado["perguntas_de_esclarecimento"]:
            print(
                f"   ? Perguntas: {resultado['perguntas_de_esclarecimento']}")
        print("-" * 60)
        time.sleep(13)

    def test_importacao_e_bases_existem():
        """Valida offline que o pipeline importa e o arquivo de pedidos existe."""
        assert callable(triar_pedido)
        assert os.path.exists(PEDIDOS_JSON_PATH)    


if __name__ == "__main__":
    # rodar_cenarios_sinteticos()
    rodar_pedidos_json(limite=15)
