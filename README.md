Assistente de IA para a cooperativa Sabor da Terra que organiza pedidos, consulta documentos e avisa os produtores.

## Interface, integração e deploy (Cloud/Fullstack/DevOps)

### Rodar localmente
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # preencha GEMINI_API_KEY
streamlit run app.py
```
Testes: `python -m pytest -q tests`

### Como cada módulo entra no assistente
O orquestrador (`core/`) não tem regra de negócio: ele carrega as ferramentas que cada
pessoa publica e as entrega ao Gemini (function calling). Para integrar o seu módulo:

1. Crie um arquivo de ferramentas no seu pacote, ex.: `sabor_triagem/tool.py`.
2. Cada função precisa de type hints, docstring dizendo **quando** usar e retorno dict/list.
3. Opcional: `TOOLS = [f1, f2]` para escolher exatamente quais funções expor.
4. Confirme que o caminho está em `TOOL_MODULES` (`.env`). Nomes padrão:
   `sabor_rag.tool`, `sabor_triagem.tool`, `sabor_agentes.tool` e `sabor_dados.tool`.
5. Acrescente as dependências do seu módulo ao `requirements.txt`.

A barra lateral do app mostra quais módulos já estão integrados e quais estão "aguardando".
O prompt de sistema final vem do Arquiteto de Prompts em `prompts/system_prompt.md`; enquanto ele
não existir, o app usa um prompt mínimo de integração.

### Deploy no Google Cloud (Cloud Run)
```bash
PROJECT_ID=seu-projeto GEMINI_API_KEY=sua-chave ./deploy/setup_gcp.sh   # 1x
PROJECT_ID=seu-projeto APP_PASSWORD=senha-da-demo ./deploy/deploy.sh     # a cada versão
```
- A chave fica no Secret Manager, nunca no repositório.
- Se o módulo de RAG tiver `scripts/build_index.py`, `deploy/entrypoint.sh` cria o índice na subida.
- `cloudbuild.yaml`: com um gatilho na `main`, cada merge roda os testes e publica uma nova revisão.
