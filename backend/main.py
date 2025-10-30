from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .normalizer import (
    Normalizer,
    load_default_mapping,
    load_mapping_from_file,
    save_mapping_to_file,
)
from .scraper import Source, collect_from_sources, merge_price_db, write_price_db
from .agent import search_prices_for_terms_http, search_prices_for_terms_headless
from .utils import RateLimiter, log_json


# Base dirs
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
LISTS_DIR = DATA_DIR / "lists"
QUOTES_DIR = DATA_DIR / "quotes"
PRICE_DB_DIR = DATA_DIR / "price_db"
PRICE_DB_FILE = PRICE_DB_DIR / "banco_de_precos.json"


def ensure_data_dirs() -> None:
    for d in (DATA_DIR, LISTS_DIR, QUOTES_DIR, PRICE_DB_DIR):
        d.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ts_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


DEFAULT_PRICE_DB: Dict[str, Dict[str, float]] = {}


def _normalize_price_db(db: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    norm: Dict[str, Dict[str, float]] = {}
    for market, items in db.items():
        norm_items: Dict[str, float] = {}
        for name, price in items.items():
            norm_items[name.lower()] = float(price)
        norm[market.lower()] = norm_items
    return norm


def load_price_db() -> Dict[str, Dict[str, float]]:
    ensure_data_dirs()
    if PRICE_DB_FILE.exists():
        try:
            with PRICE_DB_FILE.open("r", encoding="utf-8") as f:
                db = json.load(f)
            return _normalize_price_db(db)
        except Exception:
            return {}
    # Não cria base padrão; retorna vazio até o agente popular
    return {}


class ListaDeCompraUsuario(BaseModel):
    itens: List[str]


class QuoteResult(BaseModel):
    requested_at: str
    source: str
    currency: str
    cotacoes_detalhadas: Dict[str, List[Dict[str, Any]]]
    totais_por_mercado: Dict[str, float]


app = FastAPI(
    title="Servidor de Cotação (MCP)",
    description=(
        "API para cotar preços de itens de supermercado, salvar listas e histórico de cotações."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional API key and simple rate limiter
API_KEY = os.getenv("API_KEY")
RATE_MAX = int(os.getenv("RATE_MAX", "120"))
RATE_WINDOW = int(os.getenv("RATE_WINDOW", "60"))
limiter = RateLimiter(RATE_MAX, RATE_WINDOW)


def auth_dep(request: Request):
    if API_KEY:
        provided = request.headers.get("x-api-key")
        if provided != API_KEY:
            raise HTTPException(status_code=401, detail="API key inválida")
    client_ip = request.client.host if request.client else "unknown"
    key = f"ip:{client_ip}"
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="Rate limit excedido")
    return True


@app.get("/")
def health(dep: bool = Depends(auth_dep)) -> Dict[str, str]:
    return {"status": "ok", "service": "cotador", "time": now_iso()}


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def list_json_files(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    return sorted([p for p in directory.glob("*.json") if p.is_file()])


def run_quote(itens: List[str], price_db: Dict[str, Dict[str, float]], normalizer: Optional[Normalizer] = None) -> QuoteResult:
    cotacoes_finais: Dict[str, List[Dict[str, Any]]] = {}
    totais_por_mercado: Dict[str, float] = {}

    for nome_mercado, precos_do_mercado in price_db.items():
        lista_de_itens_mercado: List[Dict[str, Any]] = []
        total_mercado = 0.0

        for item_buscado in itens:
            termo = item_buscado.strip().lower()
            if normalizer is not None:
                termo = normalizer.normalize(termo)
            if not termo:
                continue
            encontrado: Optional[str] = None
            preco = 0.0
            for item_db, preco_db in precos_do_mercado.items():
                if termo in item_db:
                    encontrado = item_db
                    preco = float(preco_db)
                    total_mercado += preco
                    break

            if encontrado:
                lista_de_itens_mercado.append(
                    {
                        "item_buscado": item_buscado,
                        "item_encontrado": encontrado,
                        "preco": preco,
                    }
                )
            else:
                lista_de_itens_mercado.append(
                    {
                        "item_buscado": item_buscado,
                        "item_encontrado": "Item não encontrado neste mercado",
                        "preco": 0.0,
                    }
                )

        cotacoes_finais[nome_mercado] = lista_de_itens_mercado
        totais_por_mercado[nome_mercado] = round(total_mercado, 2)

    return QuoteResult(
        requested_at=now_iso(),
        source="real",
        currency="BRL",
        cotacoes_detalhadas=cotacoes_finais,
        totais_por_mercado=totais_por_mercado,
    )


@app.post("/lista/", status_code=201)
def salvar_lista(lista_usuario: ListaDeCompraUsuario, dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    ensure_data_dirs()
    timestamp = ts_for_filename()
    payload = {
        "itens": lista_usuario.itens,
        "saved_at": now_iso(),
    }
    path = LISTS_DIR / f"lista_{timestamp}.json"
    save_json(path, payload)
    save_json(LISTS_DIR / "latest.json", payload)
    return {"id": f"lista_{timestamp}", "path": str(path.relative_to(ROOT_DIR))}


@app.get("/listas/")
def listar_listas(dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    files = list_json_files(LISTS_DIR)
    return {
        "count": len(files),
        "items": [str(p.relative_to(ROOT_DIR)) for p in files],
    }


@app.post("/cotar/")
def fazer_cotacao(lista_usuario: ListaDeCompraUsuario, dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    ensure_data_dirs()
    _ = salvar_lista(lista_usuario)

    price_db = load_price_db()
    # Se base estiver vazia, tenta coletar fontes padrão via agente e popular a base
    if not price_db:
        try:
            from .scraper import collect_from_sources
            from .scraper import Source as ScraperSource

            sources_path = DATA_DIR / "agents" / "sources.json"
            sources_list: List[dict] = []
            if sources_path.exists():
                with sources_path.open("r", encoding="utf-8") as f:
                    sources_list = json.load(f)
            # fallback: tenta usar os 4 sites padrão se arquivo não existir
            if not sources_list:
                sources_list = [
                    {"name": "kawakami_marilia", "base_url": "https://www.kawakami.com.br/", "kind": "agent"},
                    {"name": "tauste_marilia", "base_url": "https://tauste.com.br/marilia/", "kind": "agent"},
                    {"name": "amigao", "base_url": "https://www.amigao.com/", "kind": "agent"},
                    {"name": "confianca_marilia", "base_url": "https://www.confianca.com.br/marilia", "kind": "agent"},
                ]
            sources = [ScraperSource(**s) for s in sources_list]
            updates = asyncio.run(collect_from_sources(sources))
            # carregar normalizer
            norm_path = DATA_DIR / "normalization" / "synonyms.json"
            mapping = load_default_mapping()
            mapping.update(load_mapping_from_file(norm_path))
            normalizer = Normalizer(mapping)
            merged = merge_price_db({}, updates, normalizer)
            write_price_db(PRICE_DB_FILE, merged)
            price_db = load_price_db()
        except Exception:
            price_db = {}
    norm_path = DATA_DIR / "normalization" / "synonyms.json"
    mapping = load_default_mapping()
    mapping.update(load_mapping_from_file(norm_path))
    normalizer = Normalizer(mapping)

    quote = run_quote(lista_usuario.itens, price_db, normalizer)

    # Se nada foi encontrado (todos os totais 0), tenta busca direta por termos
    all_zero = all(v == 0 for v in quote.totais_por_mercado.values()) if quote.totais_por_mercado else True
    if all_zero and lista_usuario.itens:
        try:
            # carrega sources
            sources_path = DATA_DIR / "agents" / "sources.json"
            sources_list: List[dict] = []
            if sources_path.exists():
                with sources_path.open("r", encoding="utf-8") as f:
                    sources_list = json.load(f)
            if not sources_list:
                sources_list = [
                    {"name": "kawakami_marilia", "base_url": "https://www.kawakami.com.br/", "kind": "headless"},
                    {"name": "tauste_marilia", "base_url": "https://tauste.com.br/marilia/", "kind": "agent"},
                    {"name": "amigao", "base_url": "https://www.amigao.com/", "kind": "headless"},
                    {"name": "confianca_marilia", "base_url": "https://www.confianca.com.br/marilia", "kind": "headless"},
                ]

            updates: Dict[str, Dict[str, float]] = {}
            # Busca por termos por fonte
            for s in sources_list:
                base = s.get("base_url")
                kind = (s.get("kind") or "agent").lower()
                prices: Dict[str, float] = {}
                if kind == "headless":
                    prices = asyncio.run(search_prices_for_terms_headless(base, lista_usuario.itens))  # type: ignore[arg-type]
                else:
                    prices = asyncio.run(search_prices_for_terms_http(base, lista_usuario.itens))  # type: ignore[arg-type]
                try:
                    log_json("search_terms_result", source=base, kind=kind, count=len(prices))
                except Exception:
                    pass
                updates[s["name"].lower()] = {k.lower(): float(v) for k, v in prices.items()}

            # merge e persistir
            merged = merge_price_db(price_db, updates, normalizer)
            write_price_db(PRICE_DB_FILE, merged)
            price_db = merged
            quote = run_quote(lista_usuario.itens, price_db, normalizer)
        except Exception as e:
            try:
                log_json("search_terms_error", error=str(e))
            except Exception:
                pass

    timestamp = ts_for_filename()
    quote_doc = quote.model_dump()
    quote_doc["requested_items"] = lista_usuario.itens
    quote_path = QUOTES_DIR / f"cotacao_{timestamp}.json"
    save_json(quote_path, quote_doc)
    save_json(QUOTES_DIR / "latest.json", quote_doc)

    try:
        log_json("cotacao_ok", timestamp=timestamp, totals=quote.totais_por_mercado)
    except Exception:
        pass

    return quote_doc


@app.get("/cotacoes/")
def listar_cotacoes(dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    files = list_json_files(QUOTES_DIR)
    return {
        "count": len(files),
        "items": [str(p.relative_to(ROOT_DIR)) for p in files],
    }


@app.get("/cotacoes/{cotacao_id}")
def obter_cotacao(cotacao_id: str, dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    fname = f"{cotacao_id}.json" if not cotacao_id.endswith(".json") else cotacao_id
    path = QUOTES_DIR / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cotação não encontrada")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.delete("/cotacoes/")
def limpar_cotacoes(dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    deleted = 0
    if QUOTES_DIR.exists():
        for p in QUOTES_DIR.glob("*.json"):
            try:
                p.unlink(missing_ok=True)
                deleted += 1
            except Exception:
                continue
    return {"deleted": deleted}


@app.get("/cotacoes_summary")
def summary_cotacoes(limit: int = 20, dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    files = list_json_files(QUOTES_DIR)
    files = files[-limit:] if limit > 0 else files
    out = []
    for p in reversed(files):
        try:
            with p.open("r", encoding="utf-8") as f:
                doc = json.load(f)
            totals = doc.get("totais_por_mercado", {})
            # Ignora mercados com total 0 ao escolher o melhor
            filtered = {k: v for k, v in totals.items() if v and v > 0}
            if filtered:
                best_market = min(filtered, key=filtered.get)
                best_total = filtered[best_market]
            else:
                best_market = None
                best_total = None
            out.append(
                {
                    "id": p.stem,
                    "requested_at": doc.get("requested_at"),
                    "best_market": best_market,
                    "best_total": best_total,
                }
            )
        except Exception:
            continue
    return {"count": len(out), "items": out}


class UpdatePricesRequest(BaseModel):
    sources: List[dict]


@app.post("/atualizar_precos/")
async def atualizar_precos(req: UpdatePricesRequest, dep: bool = Depends(auth_dep)) -> Dict[str, Any]:
    sources = [Source(**s) for s in req.sources]
    updates = await collect_from_sources(sources)

    norm_path = DATA_DIR / "normalization" / "synonyms.json"
    mapping = load_default_mapping()
    mapping.update(load_mapping_from_file(norm_path))
    normalizer = Normalizer(mapping)

    current = load_price_db()
    merged = merge_price_db(current, updates, normalizer)
    write_price_db(PRICE_DB_FILE, merged)

    log_json("price_db_updated", markets=list(updates.keys()))
    return {"updated_markets": list(updates.keys()), "count": len(updates)}


# Nota: para executar localmente
# uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
