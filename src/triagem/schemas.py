from typing import Literal, Optional
from pydantic import BaseModel, Field

CodigoFlag = Literal[
    "FORA_DE_SAFRA",
    "QTD_ACIMA_CAPACIDADE",
    "PRODUTO_NAO_IDENTIFICADO",
    "PRAZO_AMBIGUO",
    "QUANTIDADE_AMBIGUA",
    "DADOS_COMPRADOR_AUSENTES",
    "URGENTE",
    "SEM_PRODUTOR_ORGANICO"
]

class Comprador(BaseModel):
    nome: Optional[str] = Field(None, description="Nome da empresa, restaurante ou órgão")
    tipo: Literal["restaurante", "mercado", "governo", "desconhecido"] = "desconhecido"
    contato: Optional[str] = Field(None, description="Telefone, e-mail ou nome do responsável")

class ItemPedido(BaseModel):
    texto_original: str = Field(description="Trecho exato como escrito no pedido")
    produto: str = Field(description="Nome normalizado conforme catálogo ou 'DESCONHECIDO'")
    quantidade: Optional[float] = Field(None, description="Número exato. Null se vago como 'umas caixas'")
    unidade: Optional[str] = Field(None, description="kg, caixa, litro, unidade, etc. Null se ausente")
    producao: Literal["convencional", "organico", "nao_informado"] = "nao_informado"

class PrazoEntrega(BaseModel):
    texto_original: Optional[str] = Field(None, description="Como o prazo foi escrito (ex: 'pra sexta')")
    data_estimada: Optional[str] = Field(None, description="Data YYYY-MM-DD resolvida a partir da data_referencia")

class FlagAlerta(BaseModel):
    codigo: CodigoFlag
    item: Optional[str] = Field(None, description="Produto relacionado ao alerta, se aplicável")
    detalhe: str

class PedidoTriado(BaseModel):
    pedido_id: Optional[str] = None
    comprador: Comprador
    itens: list[ItemPedido]
    prazo: PrazoEntrega
    urgencia: Literal["alta", "media", "baixa"] = "media"
    justificativa_urgencia: str = Field(description="Breve motivo da classificação de urgência")
    status: Literal["pronto", "revisar", "bloqueado"] = "pronto"
    flags: list[FlagAlerta] = []
    campos_ausentes: list[str] = []
    perguntas_de_esclarecimento: list[str] = Field(
        description="Perguntas objetivas para fazer ao comprador caso falte dado ou haja ambiguidade"
    )

class IntencaoUsuario(BaseModel):
    rota: Literal["novo_pedido", "consulta_documentos", "relatorio_ou_dados", "conversa_geral"]
    justificativa: str