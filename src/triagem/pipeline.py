import logging
from .schemas import PedidoTriado, Comprador, PrazoEntrega
from .parser import extrair_pedido_llm
from .regras import aplicar_regras_negocio
from .prompts import CATALOGO_OFICIAL

logger = logging.getLogger(__name__)

def triar_pedido(
    texto: str,
    data_referencia: str,
    catalogo_produtos: list[str] = CATALOGO_OFICIAL,
    pedido_id: str | None = None
) -> dict:
    try:
        pedido = extrair_pedido_llm(texto, catalogo_produtos, data_referencia)
        pedido.pedido_id = pedido_id
        pedido = aplicar_regras_negocio(
            pedido, data_referencia, catalogo_produtos
        )
        return pedido.model_dump()
    except Exception:
        logger.exception("Falha na triagem do pedido %s", pedido_id)
        fallback = PedidoTriado(
            pedido_id=pedido_id,
            comprador=Comprador(),
            itens=[],
            prazo=PrazoEntrega(),
            status="revisar",
            justificativa_urgencia="Erro técnico no processamento automático.",
            perguntas_de_esclarecimento=[f"Não consegui processar este pedido automaticamente. Revise manualmente."]
        )
        return fallback.model_dump()