"""Ferramentas de consulta SQL para o orquestrador.

Reúne as ferramentas que consultam o banco SQLite
(`data/sabor_da_terra.db`) com dados estruturados da cooperativa:
produtores, preços, faturamento, sazonalidade, estoque e pedidos.

Atributos:
    TOOLS (list[Callable]): ferramentas disponíveis para o orquestrador.

Pré-requisitos:
    - Banco populado com: `python -m src.database.carregar_sql`
"""
from src.agents.ferramentas_sql import (
    consultar_estoque_lotes,
    consultar_faturamento_por_produtor,
    consultar_lote,
    consultar_pedidos,
    consultar_precos,
    consultar_produtores,
    consultar_sazonalidade,
)

TOOLS = [
    consultar_produtores,
    consultar_precos,
    consultar_faturamento_por_produtor,
    consultar_sazonalidade,
    consultar_estoque_lotes,
    consultar_lote,
    consultar_pedidos,
]
