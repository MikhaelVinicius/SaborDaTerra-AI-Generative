from .schemas import PedidoTriado, Comprador, PrazoEntrega
from .parser import extrair_pedido_llm
from .regras import aplicar_regras_negocio

def triar_pedido(
    texto: str,
    data_referencia: str,
    catalogo_produtos: list[str],
    fn_get_sazonalidade,
    fn_get_produtores,
    pedido_id: str | None = None
) -> dict:
    try:
        pedido = extrair_pedido_llm(texto, catalogo_produtos, data_referencia)
        pedido.pedido_id = pedido_id
        pedido = aplicar_regras_negocio(
            pedido, data_referencia, catalogo_produtos, fn_get_sazonalidade, fn_get_produtores
        )
        return pedido.model_dump()
    except Exception as e:
        fallback = PedidoTriado(
            pedido_id=pedido_id,
            comprador=Comprador(),
            itens=[],
            prazo=PrazoEntrega(),
            status="revisar",
            justificativa_urgencia="Erro técnico no processamento automático.",
            perguntas_de_esclarecimento=[f"Revisão manual necessária: {str(e)}"]
        )
        return fallback.model_dump()