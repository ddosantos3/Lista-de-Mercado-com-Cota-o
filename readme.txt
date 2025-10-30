Cotador de Compras — Agregador de Preços (Backend + Web + Mobile)

Resumo

Este projeto transforma uma lista de compras do usuário em cotações reais coletadas em supermercados locais. Ele combina:
- Backend FastAPI com persistência local (JSON) e integração com “agentes” de coleta (scrapers HTTP e headless via Playwright).
- Frontend web (HTML + Tailwind) para digitar itens, cotar e visualizar histórico.
- App mobile (Expo/React Native) para mesma experiência no celular.

Diferenciais

- Preço real: sem base simulada — os agentes buscam preços nos sites de mercado e salvam em data/price_db/banco_de_precos.json.
- Fallback inteligente: se uma cotação não encontra valores, o backend pesquisa por termo em cada fonte, incluindo sinônimos e versões sem acentos, e refaz a cotação.
- Headless opcional: sites SPA são renderizados via Playwright (Chromium) para extrair preços.
- Histórico persistente: cada cotação é salva em data/quotes/ e pode ser reaberta. Há botão “Limpar histórico”.
- Normalização: mapeamento básico de sinônimos para casar termos (“feijao” → “feijão carioca 1kg”).

Arquitetura

- backend/
  - main.py: API FastAPI (cotar, salvar listas, histórico, limpar histórico, atualizar preços)
  - agent.py: regras por domínio; scraping HTTP e headless; busca por termo
  - scraper.py: registro de scrapers (“agent”, “headless”, “html”, “mock”)
  - normalizer.py: sinônimos e normalização
  - utils.py: logging JSON e rate‑limiter em memória
- frontend/
  - index.html: UI com Tailwind (lista, cotação, resultados e histórico c/ limpar)
- mobile/
  - App.js: app Expo/React Native (lista, cotação, resultados e histórico)
- data/
  - price_db/banco_de_precos.json: base real de preços (gerada pelos agentes)
  - agents/sites.json: seletores e rotas de busca por domínio
  - agents/sources.json: fontes padrão (kinds: agent/headless)
  - quotes/: cotações salvas

Endpoints Principais

- POST /cotar/ → recebe {itens:[...]}, salva lista, cote em todas as fontes e persiste cotação
- GET  /cotacoes_summary?limit=20 → resumo das últimas cotações (ignora totais 0 para melhor mercado)
- GET  /cotacoes/{id} → cotação específica
- DELETE /cotacoes/ → limpa histórico (remove JSONs em data/quotes/)
- POST /atualizar_precos/ → atualiza base usando fontes informadas (kinds: agent, headless, html, mock)

Requisitos

- Python 3.11+ (recomendado virtualenv)
- Node.js LTS + npm/yarn (para o app mobile)
- Playwright (para headless)

Instalação (backend)

1) Criar venv e instalar dependências
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1   # Windows PowerShell
   # ou
   # source .venv/bin/activate       # macOS/Linux

   pip install -r requirements.txt
   python -m playwright install chromium

2) Rodar backend
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

3) Abrir frontend
   Abra frontend/index.html no navegador.

4) App mobile (opcional)
   cd mobile
   npm install
   npx expo start
   # Emulador Android usa http://10.0.2.2:8000; iOS usa http://127.0.0.1:8000.
   # Para dispositivo físico, defina EXPO_PUBLIC_API_BASE="http://SEU_IP_LAN:8000".

Configuração dos Agentes

- data/agents/sites.json: defina seletores (card/name/price) e rotas de busca por domínio (search_templates com {q}).
- data/agents/sources.json: defina as fontes padrão e sua estratégia:
  - kind "agent" → HTTP + BeautifulSoup
  - kind "headless" → Playwright (SPA)

Fluxo de Cotação (alto nível)

1) Usuário envia itens → POST /cotar/ salva lista.
2) Backend tenta cotar usando data/price_db/ (se vazio, popula usando sources.json).
3) Se todos os totais forem 0, busca por termo em cada fonte (sinônimos + sem acentos), atualiza base e refaz a cotação.
4) Resultado é salvo em data/quotes/ e retornado ao cliente.

Notas de Produção

- Autenticação: opcional por X-API-Key (defina env API_KEY). Rate limiting simples via memória (RATE_MAX/RATE_WINDOW).
- Logs: estruturados (JSON) via log_json()
- Persistência: JSON local para protótipo; recomendo migrar para Postgres em produção.
- Scraping: ajustar seletores/rotas de busca por domínio, e considerar integrações oficiais/APIs quando disponíveis.

Roadmap Sugerido

- Adaptadores de API por plataforma (ex.: VTEX, VipCommerce) para evitar headless quando possível.
- Ranking por similaridade e filtro por unidade/embalagem.
- Mapeamento de catálogo e SKU por mercado.
- Observabilidade (métricas, tracing) e fila para scraping periódico.

Como subir este projeto no GitHub (repo Trabalhos)

Opção A — Este projeto como o repositório “Trabalhos”

   # no diretório raiz deste projeto
   git init
   git add .
   git commit -m "feat: cotador de compras (backend+web+mobile)"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/Trabalhos.git
   git push -u origin main

Opção B — Adicionar este projeto como subpasta em “Trabalhos” existente

   # clone seu repo Trabalhos
   git clone https://github.com/SEU_USUARIO/Trabalhos.git
   cd Trabalhos
   # copie a pasta atual para dentro, por exemplo ./cotador_de_compras
   # (no explorador de arquivos ou via comando de cópia)
   git add cotador_de_compras
   git commit -m "feat: adiciona projeto cotador_de_compras"
   git push

Boas práticas de commit

- Commits pequenos e descritivos (feat:, fix:, docs:, chore:).
- Não versionar dados sensíveis; .gitignore cobre artefatos de ambiente e históricos.

Suporte

Em caso de erro na coleta (sites SPA ou variação de layout), ajuste data/agents/sites.json (search_templates e seletores) e/ou me avise para integrar um adaptador específico de API.

