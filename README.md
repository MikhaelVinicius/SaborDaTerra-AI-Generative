# Módulo de Triagem de Pedidos (`src/triagem`)

Responsável por receber mensagens não estruturadas de compradores, extrair entidades padronizadas via **Gemini + Pydantic (Structured Outputs)** e validar as regras de negócio da cooperativa (catálogo oficial, sazonalidade, produtores ativos, certificação orgânica e prazos).

## Arquitetura do Módulo

O fluxo combina extração via LLM com regras determinísticas em Python:

1. **Extração (`parser.py`, `prompts.py`, `schemas.py`):** Converte o texto livre em um objeto tipado (`PedidoTriado`), normalizando comprador, itens, quantidades, unidades, tipo de produção e prazo de entrega, com *retry* automático para instabilidades de API.
2. **Validação (`regras.py`):** Cruza os itens extraídos com as bases tratadas (`produtores_tratado.csv` e `sazonalidade_tratado.csv`) usando busca por aproximação (`RapidFuzz >= 75%`) e aplica as regras comerciais e agrícolas.
3. **Orquestração (`pipeline.py`):** Centraliza a execução da triagem e retorna um dicionário JSON serializável com o status final, flags de alerta e perguntas de esclarecimento.

## Estrutura de Arquivos

```text
src/triagem/
├── __init__.py
├── README.md        # Documentação específica do módulo
├── schemas.py       # Modelos Pydantic (PedidoTriado, ItemPedido, FlagAlerta)
├── prompts.py       # Instruções de sistema para extração estruturada
├── parser.py        # Cliente Google GenAI SDK com Structured Outputs e retry
├── regras.py        # Regras determinísticas de negócio e fuzzy matching
└── pipeline.py      # Ponto de entrada (triar_pedido) e montagem da resposta

tests/
└── test_triagem.py  # Testes unitários e validação dos 15 pedidos reais
```

## Classificação de Status (`status`)

- **`pronto`**: Todos os itens válidos, dentro da safra, com produtor ativo e sem pendências de informação.
- **`revisar`**: Pedido válido que exige atenção ou esclarecimento (`URGENTE` <= 48h, `SAFRA_BAIXA`, `PRAZO_AMBIGUO`, `QUANTIDADE_AMBIGUA`, `DADOS_COMPRADOR_AUSENTES`, `SEM_ITENS_IDENTIFICADOS`).
- **`bloqueado`**: Impedimento operacional que inviabiliza o atendimento automático (`PRODUTO_NAO_IDENTIFICADO`, `FORA_DE_SAFRA`, `SEM_PRODUTOR_ATIVO`, `SEM_PRODUTOR_ORGANICO`).

## Configuração e Uso

### 1. Dependências e Variáveis de Ambiente
Certifique-se de instalar as bibliotecas do módulo (`google-genai`, `pydantic`, `rapidfuzz`, `pandas`) e configurar no `.env`:

```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.8-flash
```

### 2. Chamada em Python

```python
from src.triagem.pipeline import triar_pedido

resultado = triar_pedido(
    texto="Bom dia! Aqui é Marcos do Mercado Bom Preço. Preciso de 50 kg de queijo coalho para o dia 20/11.",
    data_referencia="2026-11-15",
    pedido_id="PED-2026-001",
)
```

## Como Testar

Na raiz do projeto, execute a suíte de validação do módulo:

```bash
python -m tests.test_triagem
```

Os logs detalhados da validação com os 15 pedidos reais (`PED-2026-001` a `PED-2026-015`) estão registrados em `log_triagem.txt`.