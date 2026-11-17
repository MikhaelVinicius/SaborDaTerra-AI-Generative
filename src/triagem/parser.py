import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError
from .schemas import PedidoTriado, IntencaoUsuario
from .prompts import PROMPT_ROTEADOR, montar_prompt_extracao

load_dotenv()

MODELO = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()
    return _client

def classificar_intencao(mensagem: str, historico_recente: str = "") -> IntencaoUsuario:
    conteudo = f"<historico>\n{historico_recente}\n</historico>\n<mensagem>\n{mensagem}\n</mensagem>"
    resp = _get_client().models.generate_content(
        model=MODELO,
        contents=conteudo,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT_ROTEADOR,
            response_mime_type="application/json",
            response_schema=IntencaoUsuario,
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    )
    return IntencaoUsuario.model_validate_json(resp.text)


def extrair_pedido_llm(
    texto_pedido: str,
    catalogo_produtos: list[str],
    data_referencia: str,
    pedido_pendente: PedidoTriado | dict | str | None = None,
    tentativas: int = 2
) -> PedidoTriado:
    system_prompt = montar_prompt_extracao(catalogo_produtos, data_referencia)
    
    bloco_pendente = ""
    if pedido_pendente is not None:
        conteudo_pendente = (
            pedido_pendente.model_dump_json(indent=2)
            if isinstance(pedido_pendente, PedidoTriado)
            else str(pedido_pendente)
        )
        bloco_pendente = f"<pedido_pendente>\n{conteudo_pendente}\n</pedido_pendente>\n"

    prompt_atual = (
        f"Extraia os dados da seguinte mensagem:\n"
        f"{bloco_pendente}<pedido>\n{texto_pedido}\n</pedido>"
    )
    ultimo_erro = None

    for tentativa in range(tentativas + 1):
        try:
            resp = _get_client().models.generate_content(
                model=MODELO,
                contents=prompt_atual,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=PedidoTriado,
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                )
            )
            return PedidoTriado.model_validate_json(resp.text)
        except ValidationError as erro:
            ultimo_erro = erro
            prompt_atual += f"\n\nSua saída anterior falhou na validação de schema: {erro}. Corrija."
        except Exception as erro_api:
            ultimo_erro = erro_api
            msg_erro = str(erro_api)
            if "429" in msg_erro or "RESOURCE_EXHAUSTED" in msg_erro:
                break
            if tentativa < tentativas:
                espera = 5 * \
                    (tentativa + 1) if "503" in msg_erro else (2 ** tentativa)
                time.sleep(espera)

    raise ValueError(
        f"Falha na extração após {tentativas + 1} tentativas: {ultimo_erro}")
