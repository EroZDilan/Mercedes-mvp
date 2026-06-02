"""Agente ligero de almacén — corre en cada laptop."""
from fastapi import FastAPI, HTTPException, Header
import json
import os

app = FastAPI()

AGENT_TOKEN = os.getenv("AGENT_TOKEN", "token-alm-a")
STOCK_FILE = os.getenv("STOCK_FILE", "stock_local.json")


@app.get("/stock")
def get_stock(authorization: str = Header(...)):
    if authorization != f"Bearer {AGENT_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    with open(STOCK_FILE) as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "online"}
