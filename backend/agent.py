from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from .utils import log_json
from .normalizer import load_default_mapping

# Base path to load custom site rules
ROOT_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT_DIR / "data" / "agents"
SITES_FILE = AGENTS_DIR / "sites.json"


CURRENCY_RE = re.compile(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*|[0-9]+),([0-9]{2})")


def parse_brl(value: str) -> Optional[float]:
    m = CURRENCY_RE.search(value)
    if not m:
        return None
    inteiro, centavos = m.groups()
    inteiro = inteiro.replace(".", "")
    try:
        return float(f"{inteiro}.{centavos}")
    except Exception:
        return None


@dataclass
class SiteRule:
    domain: str
    paths: List[str] = field(default_factory=lambda: ["/"])
    search_templates: List[str] = field(default_factory=list)  # e.g. ["/catalogsearch/result/?q={q}"]
    card_selectors: List[str] = field(
        default_factory=lambda: [
            ".product",
            ".product-card",
            ".produto",
            ".item",
            ".offer",
            ".oferta",
            ".card",
            ".promo",
        ]
    )
    name_selectors: List[str] = field(
        default_factory=lambda: [
            ".name",
            ".title",
            ".product-name",
            ".descricao",
            ".desc",
            "h3",
            "h2",
            ".titulo",
        ]
    )
    price_selectors: List[str] = field(
        default_factory=lambda: [
            ".price",
            ".preco",
            ".valor",
            ".price-current",
            ".value",
            ".preco-atual",
        ]
    )


DEFAULT_RULES: List[SiteRule] = [
    SiteRule(domain="kawakami.com.br", paths=["/", "/ofertas", "/promocoes", "/promocao"]),
    SiteRule(domain="tauste.com.br", paths=["/marilia/", "/ofertas", "/promocoes"]),
    SiteRule(domain="amigao.com", paths=["/", "/ofertas", "/promocoes"]),
    SiteRule(domain="confianca.com.br", paths=["/marilia", "/ofertas", "/promocoes"]),
]

def _rule_from_dict(domain: str, data: Dict) -> SiteRule:
    return SiteRule(
        domain=domain,
        paths=list(data.get("paths", [])) or ["/"],
        card_selectors=list(data.get("card_selectors", [])) or SiteRule(domain).card_selectors,
        name_selectors=list(data.get("name_selectors", [])) or SiteRule(domain).name_selectors,
        price_selectors=list(data.get("price_selectors", [])) or SiteRule(domain).price_selectors,
        search_templates=list(data.get("search_templates", [])) or [],
    )


def load_site_rules() -> List[SiteRule]:
    if not SITES_FILE.exists():
        return DEFAULT_RULES
    try:
        import json

        with SITES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        rules: List[SiteRule] = []
        for domain, cfg in data.items():
            rules.append(_rule_from_dict(domain, cfg))
        # Merge: rules from file override defaults for same domain
        defaults_by_domain = {r.domain: r for r in DEFAULT_RULES}
        file_by_domain = {r.domain: r for r in rules}
        merged_domains = set(defaults_by_domain) | set(file_by_domain)
        merged: List[SiteRule] = []
        for d in merged_domains:
            merged.append(file_by_domain.get(d) or defaults_by_domain[d])
        return merged
    except Exception as e:  # noqa: BLE001
        log_json("agent_rules_load_error", error=str(e))
        return DEFAULT_RULES


def choose_rule(url: str, rules: List[SiteRule]) -> Optional[SiteRule]:
    for r in rules:
        if r.domain in url:
            return r
    return None


async def fetch_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        })
        r.raise_for_status()
        return r.text
    except Exception as e:  # noqa: BLE001
        log_json("agent_fetch_error", url=url, error=str(e))
        return None


def extract_from_cards(soup: BeautifulSoup, rule: SiteRule) -> Dict[str, float]:
    items: Dict[str, float] = {}
    for card_sel in rule.card_selectors:
        for card in soup.select(card_sel):
            name_text = None
            price_val: Optional[float] = None

            # Extract name
            for ns in rule.name_selectors:
                el = card.select_one(ns)
                if el and el.get_text(strip=True):
                    name_text = el.get_text(" ", strip=True)
                    break
            if not name_text:
                # fallback: text of card
                name_text = card.get_text(" ", strip=True)[:120]

            # Extract price
            for ps in rule.price_selectors:
                elp = card.select_one(ps)
                if not elp:
                    continue
                price = parse_brl(elp.get_text(" ", strip=True))
                if price is not None:
                    price_val = price
                    break
            if price_val is None:
                # fallback: search in card text
                price_val = parse_brl(card.get_text(" ", strip=True))

            if name_text and price_val is not None:
                items[name_text.lower()] = float(price_val)
        if items:
            break
    return items


def extract_fallback(soup: BeautifulSoup, limit: int = 100) -> Dict[str, float]:
    items: Dict[str, float] = {}
    # naive approach: find all elements that contain 'R$' and take preceding text as name
    for el in soup.find_all(string=re.compile(r"R\$")):
        txt = el.strip()
        price = parse_brl(txt)
        if price is None:
            continue
        # name: take parent text sans price
        parent = el.parent
        if not parent:
            continue
        ptxt = parent.get_text(" ", strip=True)
        if not ptxt:
            continue
        name = CURRENCY_RE.sub("", ptxt).strip()
        if len(name) < 3:
            continue
        items[name.lower()] = float(price)
        if len(items) >= limit:
            break
    return items


async def fetch_prices_for_url(url: str) -> Dict[str, float]:
    rules = load_site_rules()
    rule = choose_rule(url, rules)
    paths = rule.paths if rule else ["/"]
    base = url.rstrip("/")
    items: Dict[str, float] = {}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Try base URL first
        html = await fetch_html(client, base)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            if rule:
                items = extract_from_cards(soup, rule)
            if not items:
                items = extract_fallback(soup)
        # Try additional paths until we have items
        if not items:
            for p in paths:
                target = base + p if not base.endswith(p) else base
                html2 = await fetch_html(client, target)
                if not html2:
                    continue
                soup2 = BeautifulSoup(html2, "html.parser")
                if rule:
                    items = extract_from_cards(soup2, rule)
                if not items:
                    items = extract_fallback(soup2)
                if items:
                    break
    log_json("agent_prices_collected", url=url, count=len(items))
    return items


class AgentScraper:
    async def fetch_prices(self, source) -> Dict[str, float]:
        # `source.base_url` expected to be a full URL
        return await fetch_prices_for_url(source.base_url)


# ---- Headless (Playwright) Agent ----
async def fetch_prices_headless_for_url(url: str) -> Dict[str, float]:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception as e:  # noqa: BLE001
        log_json("agent_headless_import_error", error=str(e))
        return {}

    rules = load_site_rules()
    rule = choose_rule(url, rules)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="pt-BR")
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            # Pequeno scroll para carregar lazy content
            try:
                await page.evaluate(
                    "() => new Promise(res => { let y=0; const i=setInterval(()=>{ window.scrollBy(0, 800); y+=800; if(y>6000){clearInterval(i); res();}}, 150); })"
                )
            except Exception:
                pass
            html = await page.content()
        except Exception as e:  # noqa: BLE001
            log_json("agent_headless_nav_error", url=url, error=str(e))
            await context.close()
            await browser.close()
            return {}
        finally:
            # keep context open until parse complete
            pass

        soup = BeautifulSoup(html, "html.parser")
        items: Dict[str, float] = {}
        if rule:
            items = extract_from_cards(soup, rule)
        if not items:
            items = extract_fallback(soup)

        await context.close()
        await browser.close()

    log_json("agent_headless_prices_collected", url=url, count=len(items))
    return items


class AgentHeadlessScraper:
    async def fetch_prices(self, source) -> Dict[str, float]:
        return await fetch_prices_headless_for_url(source.base_url)


# ---- Per-term search helpers ----
def _build_search_urls(base_url: str, rule: SiteRule, term: str) -> List[str]:
    from urllib.parse import urljoin, quote_plus

    urls: List[str] = []
    for tpl in rule.search_templates:
        q = quote_plus(term)
        candidate = tpl.format(q=q)
        if candidate.startswith("http"):
            urls.append(candidate)
        else:
            urls.append(urljoin(base_url, candidate))
    return urls


def _expand_queries(terms: List[str]) -> Dict[str, List[str]]:
    mapping = load_default_mapping()
    expanded: Dict[str, List[str]] = {}
    def deaccent(s: str) -> str:
        import unicodedata
        return "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    for t in terms:
        t0 = (t or '').strip()
        if not t0:
            continue
        base = [t0]
        # add mapping if exists
        canon = mapping.get(t0.lower())
        if canon and canon not in base:
            base.append(canon)
        # add deaccent versions
        base.extend({deaccent(x) for x in list(base)})
        # unique preserve order
        seen = set()
        uniq = []
        for x in base:
            xl = x.lower()
            if xl in seen:
                continue
            seen.add(xl)
            uniq.append(x)
        expanded[t0] = uniq
    return expanded


async def search_prices_for_terms_http(base_url: str, terms: List[str]) -> Dict[str, float]:
    rules = load_site_rules()
    rule = choose_rule(base_url, rules)
    if not rule or not rule.search_templates:
        return {}
    out: Dict[str, float] = {}
    term_queries = _expand_queries(terms)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for term in terms:
            found_price: Optional[float] = None
            for q in term_queries.get(term, [term]):
                for url in _build_search_urls(base_url, rule, q):
                    html = await fetch_html(client, url)
                    if not html:
                        continue
                    soup = BeautifulSoup(html, "html.parser")
                    items = extract_from_cards(soup, rule)
                    if not items:
                        items = extract_fallback(soup)
                    if items:
                        # pick the first item price
                        found_price = next(iter(items.values()))
                        break
                if found_price is not None:
                    break
            if found_price is not None:
                out[term.lower()] = float(found_price)
    return out


async def search_prices_for_terms_headless(base_url: str, terms: List[str]) -> Dict[str, float]:
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception as e:  # noqa: BLE001
        log_json("agent_headless_import_error", error=str(e))
        return {}
    rules = load_site_rules()
    rule = choose_rule(base_url, rules)
    if not rule or not rule.search_templates:
        return {}
    out: Dict[str, float] = {}
    term_queries = _expand_queries(terms)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="pt-BR")
        page = await context.new_page()
        try:
            from urllib.parse import urljoin
            for term in terms:
                found_price: Optional[float] = None
                for q in term_queries.get(term, [term]):
                    for url in _build_search_urls(base_url, rule, q):
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=30000)
                            await page.evaluate(
                                "() => new Promise(res => { let y=0; const i=setInterval(()=>{ window.scrollBy(0, 1000); y+=1000; if(y>8000){clearInterval(i); res();}}, 120); })"
                            )
                            html = await page.content()
                            soup = BeautifulSoup(html, "html.parser")
                            items = extract_from_cards(soup, rule)
                            if not items:
                                items = extract_fallback(soup)
                            if items:
                                found_price = next(iter(items.values()))
                                break
                        except Exception:
                            continue
                    if found_price is not None:
                        break
                if found_price is not None:
                    out[term.lower()] = float(found_price)
        finally:
            await context.close()
            await browser.close()
    return out
