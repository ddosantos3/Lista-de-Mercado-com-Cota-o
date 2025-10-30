from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol, Tuple, Union, cast

import httpx

from .normalizer import Normalizer
from .agent import AgentScraper, AgentHeadlessScraper
from .utils import log_json


@dataclass
class Source:
    name: str
    base_url: str
    kind: str | None = None  # usado para selecionar adapter
    metadata: Dict[str, Any] | None = None


class Scraper(Protocol):
    async def fetch_prices(self, source: Source) -> Dict[str, float]:
        ...


class MockScraper:
    async def fetch_prices(self, source: Source) -> Dict[str, float]:
        # Simula um retorno de preços
        return {
            "arroz 5kg tipo 1": 27.90,
            "feijão carioca 1kg": 9.10,
            "óleo de soja 900ml": 7.55,
            "café 500g": 15.10,
            "açúcar 1kg": 5.40,
            "farinha de trigo 1kg": 5.05,
            "leite longa vida 1l": 4.10,
        }


class GenericHTMLScraper:
    def __init__(self, timeout: float = 10.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    async def fetch_prices(self, source: Source) -> Dict[str, float]:
        # Placeholder: em produção, implementar parsing específico do site
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            last_err = None
            for attempt in range(self.retries + 1):
                try:
                    r = await client.get(source.base_url)
                    r.raise_for_status()
                    # TODO: extrair preços reais do HTML
                    log_json("scraper_generic_html_ok", url=source.base_url, status=r.status_code)
                    return {}
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    log_json("scraper_generic_html_error", url=source.base_url, attempt=attempt, error=str(e))
            if last_err:
                raise last_err
        return {}


SCRAPER_REGISTRY: Dict[str, Scraper] = {
    "mock": MockScraper(),
    "html": GenericHTMLScraper(),
    "agent": AgentScraper(),
    "headless": AgentHeadlessScraper(),
}


async def collect_from_sources(sources: List[Source]) -> Dict[str, Dict[str, float]]:
    async def run_one(src: Source) -> tuple[str, Dict[str, float]]:
        kind = (src.kind or "mock").lower()
        scraper = SCRAPER_REGISTRY.get(kind, SCRAPER_REGISTRY["mock"])  # fallback
        prices = await scraper.fetch_prices(src)
        return src.name, {k.lower(): float(v) for k, v in prices.items()}

    results: List[Union[Tuple[str, Dict[str, float]], BaseException]] = await asyncio.gather(
        *(run_one(s) for s in sources), return_exceptions=True
    )
    merged: Dict[str, Dict[str, float]] = {}
    for res in results:
        # asyncio.gather returns BaseException instances on errors when return_exceptions=True
        if isinstance(res, BaseException):
            log_json("scraper_task_error", error=str(res))
            continue
        name, prices = res  # type: ignore[misc]
        # Or, to be explicit for type checkers:
        name, prices = cast(Tuple[str, Dict[str, float]], (name, prices))
        merged[name.lower()] = prices
    return merged


def merge_price_db(current: Dict[str, Dict[str, float]], updates: Dict[str, Dict[str, float]], normalizer: Normalizer) -> Dict[str, Dict[str, float]]:
    db = {mk: items.copy() for mk, items in current.items()}
    for market, items in updates.items():
        target = db.setdefault(market, {})
        for item, price in items.items():
            canon = normalizer.normalize(item)
            target[canon] = float(price)
    return db


def write_price_db(path: Path, db: Dict[str, Dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
