"""
Compat de execução: expõe `app` do backend.main.

Permite rodar `uvicorn main:app` se alguém ainda usar este caminho.
"""

from backend.main import app  # reexport app

