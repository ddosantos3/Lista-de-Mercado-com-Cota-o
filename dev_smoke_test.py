from backend.main import app, ensure_data_dirs
from fastapi.testclient import TestClient

def main():
    ensure_data_dirs()
    client = TestClient(app)

    r = client.get('/')
    print('GET / ->', r.status_code, r.json())

    payload = {"itens": ["arroz", "feijão", "óleo", "leite"]}
    r = client.post('/cotar/', json=payload)
    print('POST /cotar ->', r.status_code)
    data = r.json()
    print('keys:', list(data.keys()))
    print('totais:', data.get('totais_por_mercado'))

    r = client.get('/listas/')
    print('GET /listas ->', r.status_code, r.json().get('count'))

    r = client.get('/cotacoes/')
    print('GET /cotacoes ->', r.status_code, r.json().get('count'))

if __name__ == '__main__':
    main()

