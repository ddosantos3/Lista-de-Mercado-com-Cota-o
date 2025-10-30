import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from backend.main import app
from fastapi.testclient import TestClient
import json

client = TestClient(app)

payload = {"itens": ["feijao", "arroz", "oleo"]}
r = client.post('/cotar/', json=payload)
print('status', r.status_code)
data = r.json()
print('totais', data.get('totais_por_mercado'))
