# 🌱 Sabor da Terra — Assistente Inteligente da Cooperativa

Assistente conversacional multi-agente desenvolvido para apoiar a operação comercial, documental e logística da **Cooperativa Sabor da Terra** (Garanhuns/PE). O sistema unifica triagem automatizada de pedidos em linguagem natural, busca semântica em normas técnicas e certificações (RAG), consultas estruturadas de estoque/preços/produtores e governança de dados sensíveis.

---

## 🏗️ Arquitetura e Módulos Integrados

O projeto foi desenvolvido em frentes modulares e consolidado em uma arquitetura orientada a ferramentas (*Tool Calling*):

* **Interface, Orquestração & Cloud/DevOps (`app.py`, `core/`, `deploy/`)**
  * Interface web conversacional construída em **Streamlit** com histórico multi-turno, botão de reinício de sessão, proteção opcional por senha (`APP_PASSWORD`) e painel de transparência mostrando ferramentas acionadas, argumentos, retornos e latência (`ms`).
  * Orquestrador central (`core/orchestrator.py` e `core/integracao.py`) que descobre e acopla automaticamente as ferramentas de cada domínio.
  * Containerização com **Docker** (`Dockerfile`, `deploy/entrypoint.sh`) e pipeline de deploy automatizado para **Google Cloud Run** via **Cloud Build** (`cloudbuild.yaml`, `deploy/setup_gcp.sh`, `deploy/deploy.sh`).

* **Triagem Comercial de Pedidos (`src/triagem/`, `sabor_triagem/`)**
  * Pipeline híbrido que combina **Google Gemini (`gemini-3.5-flash-lite`)** com extração estruturada via **Pydantic** (`schemas.py`) e regras determinísticas em Python (`regras.py`).
  * Tolera mensagens informais, abreviações e erros ortográficos (estilo WhatsApp), normalizando itens do catálogo, calculando prazos e urgência (`alta` para entregas em menos de 48h), detectando ambiguidades (ex.: *mel silvestre* vs. *mel de jandaíra*) e mantendo estado incremental (`pedido_pendente`) entre turnos.

* **Base Documental & RAG (`sabor_rag/`, `data/processed/raw/documents/`)**
  * Pipeline de ingestão, limpeza/redação de dados sensíveis (`redaction.py`), *chunking* (`chunking.py`), geração de *embeddings* e busca vetorial com **ChromaDB** (`vector_store.py`, `retriever.py`).
  * Indexa certificados orgânicos, laudos sanitários (ADAGRO / SIE / Selo Arte), contratos institucionais (como PNAE) e fichas técnicas de produtos, respondendo com citação explícita das fontes.

* **Engenharia de Agentes & Consultas Estruturadas (`sabor_agent/`, `sabor_agentes/`, `docs/ferramentas-agente.md`)**
  * Conjunto de ferramentas tipadas com formatadores dedicados (`formatters.py`):
    * `get_producer_summary`: consolida vendas, volumes (kg) e status de pagamentos (`pago`, `pendente`, `unclassified`) por produtor (`Pxxx`) e intervalo de datas (`AAAA-MM-DD`).
    * `lookup_price`: consulta a tabela vigente de preços (`matches` exatos e `suggestions` de variantes) sem inferir valores inexistentes.
    * `lookup_lot`: rastreabilidade operacional de lotes com **mascaramento obrigatório de nome e CPF do produtor** por política de privacidade.

* **Tratamento de Dados & Persistência (`data/processed/`, `src/database/`, `src/agents/`)**
  * Pipelines de higienização e padronização dos datasets brutos (`produtores_tratado.csv`, `lotes_tratado.csv`, `precos_tratados.csv`, `financeiro_tratado.csv`, `sazonalidade_tratado.csv` e `pedidos.json`).
  * Carga e consulta relacional em **SQLite** (`src/database/carregar_sql.py` → `data/sabor_da_terra.db`) com ferramentas SQL dedicadas (`src/agents/ferramentas_sql.py`).

---

## 📁 Estrutura do Repositório

```text
SaborDaTerra-AI/
├── app.py                        # Aplicação principal Streamlit
├── core/                         # Configuração, LLM client, descoberta de tools e orquestrador
├── sabor_triagem/                # Adaptador de ferramenta do módulo de triagem
├── src/triagem/                  # Schemas Pydantic, parser LLM, prompts, regras e relatórios
├── sabor_rag/                    # Loader, chunking, embeddings, ChromaDB e retriever RAG
├── sabor_agent/                  # Ferramentas estruturadas (dados, formatadores e orquestrador)
├── sabor_agentes/                # Adaptador de descoberta de ferramentas para o agente
├── sabor_dados/                  # Adaptador de consulta aos dados tratados
├── src/database/                 # Carga SQLite e configuração de armazenamento
├── src/agents/                   # Ferramentas de consulta SQL
├── data/
│   └── processed/                # CSVs/JSON tratados e documentos brutos da cooperativa
├── scripts/                      # Utilitários (build_index.py, demo_data_tools.py, testes)
├── deploy/                       # Scripts de setup e deploy no Google Cloud Platform
├── docs/                         # Documentação técnica detalhada (ferramentas e RAG)
├── tests/                        # Suíte automatizada com Pytest
├── Dockerfile                    # Imagem de produção
├── cloudbuild.yaml               # Pipeline CI/CD Google Cloud Build
└── requirements.txt              # Dependências Python do projeto
```

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
* **Python 3.11+** (testado em Python 3.14)
* Chave de API do **Google Gemini** (`GEMINI_API_KEY`)

### 2. Instalação
Clone o repositório, crie o ambiente virtual e instale as dependências:

```bash
git clone https://github.com/EdieneGomes/SaborDaTerra-AI.git
cd SaborDaTerra-AI

python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuração de Variáveis de Ambiente
Copie o arquivo de exemplo e preencha sua chave da API:

```bash
cp .env.example .env
```

Principais variáveis no `.env`:
```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.5-flash-lite
APP_PASSWORD=                  # Opcional: define senha de acesso na tela inicial
MOSTRAR_FERRAMENTAS=true       # Exibe o painel técnico de chamadas de ferramentas no chat
```

### 4. Preparação dos Dados e Índice Vetorial (RAG)
Antes de iniciar a interface pela primeira vez, popule o banco SQLite e construa o índice documental do ChromaDB:

```bash
python -m src.database.carregar_sql
python -m scripts.build_index
```

### 5. Executar a Aplicação
```bash
python -m streamlit run app.py
```
A aplicação ficará disponível em `http://localhost:8501`.

---

## 🧪 Testes Automatizados

O projeto conta com suíte de testes unitários e de integração cobrindo triagem, regras de negócio, chunking/loader do RAG, formatadores, ferramentas de dados e resiliência do orquestrador:

```bash
python -m pytest tests/ -v
```

---

## ☁️ Deploy em Nuvem (Google Cloud Run)

O repositório já inclui automação para implantação conteinerizada no GCP:

1. **Configuração inicial de APIs e permissões no GCP:**
   ```bash
   bash deploy/setup_gcp.sh
   ```
2. **Build e deploy no Cloud Run:**
   ```bash
   bash deploy/deploy.sh
   ```
   *(Ou via gatilho automatizado utilizando `cloudbuild.yaml`).*

---

## 🔒 Governança e Privacidade de Dados

* **Proteção de PII:** Consultas de rastreabilidade de lotes (`lookup_lot`) omitem automaticamente nome e CPF dos produtores.
* **Recusa de Dados Sensíveis:** O assistente bloqueia solicitações de dados bancários, documentos pessoais ou informações confidenciais de cooperados.
* **Fidelidade Documental:** Respostas sobre preços, estoque e certificações são estritamente vinculadas às tabelas vigentes e documentos indexados, sinalizando indisponibilidade ou certificados vencidos sem inventar valores.

---

## 📚 Documentação Complementar

* [`docs/ferramentas-agente.md`](docs/ferramentas-agente.md) — Especificação técnica, contratos JSON Schema e regras de comportamento das ferramentas estruturadas.