from datetime import date
from src.triagem.pipeline import triar_pedido as _triar_pedido

def triar_pedido(texto_pedido: str, data_referencia: str | None = None) -> dict:
    """Realiza a triagem comercial de um pedido em linguagem natural enviado por um comprador.

    Extrai itens, quantidades, unidades, tipo de produção (orgânico/convencional) e prazo,
    validando contra o catálogo oficial, janela de safra e produtores ativos da cooperativa.
    Retorna o status ('pronto', 'revisar' ou 'bloqueado'), flags de alerta e perguntas de esclarecimento.
    """
    data_ref = data_referencia or date.today().isoformat()
    return _triar_pedido(texto=texto_pedido, data_referencia=data_ref)


TOOLS = [triar_pedido]