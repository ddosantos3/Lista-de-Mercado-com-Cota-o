Lista de Mercado com Cotação (v1.1)

Este repositório implementa a "Lista de Mercado com Cotação": um agregador de preços de supermercado com API em FastAPI, frontend web (HTML + Tailwind) e app mobile (Expo/React Native). Salva listas e cotações em disco e coleta preços reais com agentes (HTTP e Headless via Playwright).

Estrutura de Pastas

/cotador_de_compras
|
|-- /backend
|   |-- __init__.py
|   |-- main.py           # Servidor FastAPI (API e persistência local)
|
|-- /frontend
|   |-- index.html        # Interface de usuário (teste)
|
|-- requirements.txt      # Dependências do Python
|-- README.md             # Este arquivo
|-- /data                 # Persistência local (criada em runtime)
|   |-- /lists            # Listas salvas como JSON
|   |-- /quotes           # Cotações salvas como JSON
|   |-- /price_db         # Base de preços (JSON gerada pelo agente)


Como Executar

1) Crie e ative um ambiente virtual

# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

2) Instale dependências

pip install -r requirements.txt

3) Inicie o servidor backend (FastAPI)

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

O backend ficará disponível em http://127.0.0.1:8000.

4) Abra o frontend

Abra o arquivo `frontend/index.html` no navegador (duplo-clique). A comunicação entre file:// (HTML) e http:// (backend) funciona porque o CORS está habilitado. A UI agora exibe histórico de cotações e permite reabrir resultados anteriores.


Como Funciona

- O backend expõe:
  - POST /lista/         → Salva a lista do usuário em data/lists/
  - POST /cotar/         → Salva a lista e retorna cotação simulada; persiste em data/quotes/
  - GET  /listas/        → Lista os arquivos de listas salvas
- GET  /cotacoes/      → Lista os arquivos de cotações salvas
- GET  /cotacoes/{id}  → Retorna uma cotação específica
- GET  /cotacoes_summary?limit=20 → Lista resumos (mais novo primeiro)
- POST /atualizar_precos/ → Atualiza `data/price_db/` a partir de fontes (scrapers)

- A base de preços real é carregada de `data/price_db/banco_de_precos.json` e é populada pelo agente.
  - Endpoint para atualizar preços via scrapers: `POST /atualizar_precos/` com corpo `{ "sources": [{"name": "confianca_marilia", "base_url": "https://...", "kind": "agent|html|mock"}] }`.
  - `kind: "agent"` usa o agente com seletores por domínio. `kind: "html"` é um placeholder genérico para scraping HTML. `kind: "mock"` apenas para testes.
  - Personalize seletores por domínio em `data/agents/sites.json`. Exemplo de entrada:
    {
      "confianca.com.br": {
        "paths": ["/marilia", "/ofertas"],
        "card_selectors": [".product-card", ".oferta"],
        "name_selectors": [".product-name", "h3"],
        "price_selectors": [".price", ".preco"]
      }
    }
  - As regras do arquivo substituem as padrões do código quando o domínio coincide.
  - Configure as fontes padrão em `data/agents/sources.json` (usado automaticamente se o banco estiver vazio ao cotar).

- O frontend envia a lista do usuário para /cotar/ e exibe totais por mercado e itens detalhados, destacando a opção mais barata.


 Autenticação e Rate Limiting

- Se a variável de ambiente `API_KEY` estiver definida, a API exigirá o cabeçalho `X-API-Key` em todas as rotas.
- Rate limiting simples em memória: `RATE_MAX` (padrão 120) por janela `RATE_WINDOW` em segundos (padrão 60). Para produção, use um limitador com Redis.

 Normalização de Produtos

- Há um mapeamento básico de sinônimos que melhora a busca, e você pode estendê-lo em `data/normalization/synonyms.json`.

 Próximos Passos (produção)


Aplicativo Mobile (Expo)

- Pré‑requisitos: Node.js LTS e npm instalados.
- Entre na pasta `mobile/` e instale dependências:

  npm install

- Inicie no Expo:

  npx expo start

- Emuladores/Dispositivos:
  - iOS Simulator: o app usa `http://127.0.0.1:8000` por padrão.
  - Android Emulator: usa `http://10.0.2.2:8000` por padrão.
  - Dispositivo físico: defina o host da API em runtime com variável de ambiente Expo:

    EXPO_PUBLIC_API_BASE="http://SEU_IP_LAN:8000" npx expo start

  - O mobile chama os mesmos endpoints do backend, com tela de lista, cotação, resultados e histórico. Não há campo de API key no app; se necessário, configure no backend ou defina no código.

Publicando no GitHub

Este projeto deve subir no repositório:

https://github.com/ddosantos3/Lista-de-Mercado-com-Cota-o

Opção 1 — Subir diretamente deste diretório (novo repo)

git init
git add .
git commit -m "feat: Lista de Mercado com Cotação (backend + web + mobile)"
git branch -M main
git remote add origin https://github.com/ddosantos3/Lista-de-Mercado-com-Cota-o.git
git push -u origin main

Opção 2 — Se já existir um repo local “Trabalhos” e você quiser adicionar como subpasta

git clone https://github.com/ddosantos3/Lista-de-Mercado-com-Cota-o.git
cd Lista-de-Mercado-com-Cota-o
# Copie todo o conteúdo deste projeto para aqui (ou mova a pasta inteira)
git add .
git commit -m "feat: adiciona projeto Lista de Mercado com Cotação"
git push

Observação: caso seja solicitado login/token, gere um Personal Access Token (PAT) com escopo repo e utilize-o ao autenticar; ou use a GitHub CLI com `gh auth login` e `gh repo set-default`.

- Trocar a base simulada por scrapers reais (ou integrações de APIs de mercados) que atualizem `data/price_db/` periodicamente.
- Adicionar normalização e mapeamento de nomes de produtos (ex.: catálogos, sinônimos, marcas).
- Persistência robusta (ex.: Postgres) e autenticação.
- Observabilidade: logs estruturados, métricas e tracing.

