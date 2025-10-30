import asyncio
from pathlib import Path
import httpx

PAGES = {
    'kawakami.com.br': ['https://www.kawakami.com.br/', 'https://www.kawakami.com.br/ofertas', 'https://www.kawakami.com.br/promocoes', 'https://www.kawakami.com.br/promocao'],
    'tauste.com.br': ['https://tauste.com.br/marilia/', 'https://tauste.com.br/marilia/ofertas', 'https://tauste.com.br/ofertas'],
    'amigao.com': ['https://www.amigao.com/', 'https://www.amigao.com/ofertas', 'https://www.amigao.com/promocoes'],
    'confianca.com.br': ['https://www.confianca.com.br/marilia', 'https://www.confianca.com.br/marilia/ofertas', 'https://www.confianca.com.br/ofertas']
}

OUT_DIR = Path('data/agents/snapshots')
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}

async def fetch_all():
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=UA) as client:
        for domain, urls in PAGES.items():
            for idx, url in enumerate(urls):
                try:
                    r = await client.get(url)
                    p = OUT_DIR / f"{domain}_{idx}.html"
                    p.write_text(r.text, encoding='utf-8')
                    print(domain, idx, r.status_code, len(r.text))
                except Exception as e:
                    print('ERR', domain, idx, url, e)

if __name__ == '__main__':
    asyncio.run(fetch_all())

