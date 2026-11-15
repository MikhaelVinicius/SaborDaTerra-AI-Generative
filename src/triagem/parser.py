import os 
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError
from .schemas import PedidoTriado, IntencaoUsuario
from .prompts import PROMPT_ROTEADOR, montar_prompt_extracao

load_dotenv()

client = genai.Client()
MODELO = os.getenv("GEMINI_MODEL","gemini-3.8-flash")

def classificar_intencao(mensagem: str, historico_recente: str = "") -> IntencaoUsuario:
    conteudo = f"<historico>\n{historico_recente}\n</historico>\n<mensagem>\n{mensagem}\n</mensagem>"
    resp = client.models.generate_content(
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
    tentativas: int = 2
) -> PedidoTriado:
    system_prompt = montar_prompt_extracao(catalogo_produtos, data_referencia)
    prompt_atual = f"Extraia os dados do seguinte pedido:\n<pedido>\n{texto_pedido}\n</pedido>"

    for _ in range(tentativas + 1):
        resp = client.models.generate_content(
            model=MODELO,
            contents=prompt_atual,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=PedidoTriado,
                thinking_config=types.ThinkingConfig(thinking_level="low")
            )
        )
        try:
            return PedidoTriado.model_validate_json(resp.text)
        except ValidationError as erro:
            prompt_atual += f"\n\nSua saída anterior falhou na validação de schema: {erro}. Corrija."

    raise ValueError("Falha na validação Pydantic após retries.")