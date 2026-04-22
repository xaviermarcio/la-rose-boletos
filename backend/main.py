"""
LA ROSE — backend/main.py
Servidor FastAPI — processa imagens JPG/PNG de NFe e Boletos.
"""

import os
import re
import socket
import uuid
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from dotenv import load_dotenv

load_dotenv()

from ocr_engine import (
    processar_documento,
    extrair_linha_digitavel,
    extrair_valor_texto,
    extrair_vencimento_texto,
    linha_para_codigo44,
    decodificar_vencimento,
    decodificar_valor,
    ler_texto,
    OCR_ATIVO,
    LANGS,
)

import firebase_admin
from firebase_admin import credentials, firestore


# ── AUTO-IP ───────────────────────────────────────────────────────────────────

def descobrir_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

IP    = descobrir_ip()
PORTA = 8000

print(f"\n🌸  La Rose iniciando...")
print(f"📡  IP local: {IP}")
print(f"🌐  Acesse: http://localhost:{PORTA}")
print(f"📱  Celular: http://{IP}:{PORTA}")
print(f"🔬  OCR: {'Ativo (' + LANGS + ')' if OCR_ATIVO else 'Simulação'}\n")


# ── FIREBASE ──────────────────────────────────────────────────────────────────

def conectar_firebase() -> bool:
    caminho = os.getenv("FIREBASE_KEY_PATH", "firebase-key.json")
    if os.path.exists(caminho):
        cred = credentials.Certificate(caminho)
        firebase_admin.initialize_app(cred)
        print(f"✅  Firebase conectado\n")
        return True
    print(f"⚠️   Firebase não configurado — modo demo\n")
    return False

FIREBASE_ATIVO = conectar_firebase()
db = firestore.client() if FIREBASE_ATIVO else None

app = FastAPI(title="La Rose API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR     = Path(tempfile.gettempdir()) / "larose_temp"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
TEMP_DIR.mkdir(exist_ok=True)


# ── MODELOS ───────────────────────────────────────────────────────────────────

class BoletoCreate(BaseModel):
    fornecedor:      str
    loja_id:         str
    loja_nome:       str
    cnpj_loja:       str
    valor:           float
    vencimento:      str
    linha_digitavel: str
    parcela_atual:   int = 1
    total_parcelas:  int = 1
    chave_nfe:       Optional[str] = None
    data_emissao:    Optional[str] = None
    numero_nota:     Optional[str] = None

    @validator("valor")
    def valor_positivo(cls, v):
        if v <= 0:
            raise ValueError("Valor deve ser maior que zero")
        return v

    @validator("vencimento")
    def data_valida(cls, v):
        if not re.match(r"^\d{2}/\d{2}/\d{4}$", v):
            raise ValueError("Use o formato DD/MM/AAAA")
        return v


class StatusUpdate(BaseModel):
    status: str

    @validator("status")
    def status_valido(cls, v):
        if v.upper() not in {"PENDENTE", "ENVIADO", "PAGO"}:
            raise ValueError("Status inválido")
        return v.upper()


# ── HELPERS ───────────────────────────────────────────────────────────────────

def checar_duplicidade(linha: str) -> bool:
    if not db or not linha.strip():
        return False
    limpa = re.sub(r"[\s\.]", "", linha)
    docs  = db.collection("boletos").where("linha_limpa", "==", limpa).limit(1).get()
    return len(docs) > 0


# ── ARQUIVOS ESTÁTICOS ────────────────────────────────────────────────────────

@app.get("/")
async def raiz():
    return FileResponse(str(FRONTEND_DIR / "index.html"), media_type="text/html")

@app.get("/app.js")
async def servir_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="application/javascript")

@app.get("/firebase-config.js")
async def servir_firebase_config():
    caminho = FRONTEND_DIR / "firebase-config.js"
    if not caminho.exists():
        raise HTTPException(404, "firebase-config.js não encontrado.")
    return FileResponse(str(caminho), media_type="application/javascript")

@app.get("/manifest.json")
async def manifesto():
    return FileResponse(str(FRONTEND_DIR / "manifest.json"), media_type="application/json")

@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        str(FRONTEND_DIR / "sw.js"),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )

@app.get("/favicon.ico")
async def favicon():
    caminho = FRONTEND_DIR / "icons" / "icon-192.png"
    if caminho.exists():
        return FileResponse(str(caminho))
    raise HTTPException(404)

@app.get("/icons/{nome}")
async def icone(nome: str):
    caminho = FRONTEND_DIR / "icons" / nome
    if not caminho.exists():
        raise HTTPException(404)
    return FileResponse(str(caminho))


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def config():
    return {
        "ip":             IP,
        "porta":          PORTA,
        "ocr_ativo":      OCR_ATIVO,
        "firebase_ativo": FIREBASE_ATIVO,
        "langs":          LANGS,
    }


@app.post("/api/ocr")
async def processar_ocr(
    arquivo: UploadFile = File(...),
    tipo: str = "Boleto"
):
    content_type = arquivo.content_type or ""
    eh_pdf = content_type == "application/pdf" or (arquivo.filename or "").lower().endswith(".pdf")
    eh_img = content_type.startswith("image/")

    if not eh_pdf and not eh_img:
        raise HTTPException(400, "Envie JPG, PNG ou PDF.")

    ext = Path(arquivo.filename or "img.jpg").suffix or (".pdf" if eh_pdf else ".jpg")
    caminho = TEMP_DIR / f"{uuid.uuid4()}{ext}"

    try:
        conteudo = await arquivo.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)
        return JSONResponse(processar_documento(str(caminho), tipo))
    except Exception as e:
        raise HTTPException(500, f"Erro: {str(e)}")
    finally:
        if caminho.exists():
            os.remove(caminho)


@app.post("/api/codigo-rapido")
async def codigo_rapido(arquivo: UploadFile = File(...)):
    content_type = arquivo.content_type or ""
    eh_pdf = content_type == "application/pdf" or (arquivo.filename or "").lower().endswith(".pdf")
    eh_img = content_type.startswith("image/")

    if not eh_pdf and not eh_img:
        raise HTTPException(400, "Envie JPG, PNG ou PDF.")

    ext = Path(arquivo.filename or "b.jpg").suffix or (".pdf" if eh_pdf else ".jpg")
    caminho = TEMP_DIR / f"{uuid.uuid4()}{ext}"

    try:
        conteudo = await arquivo.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)

        texto = ler_texto(str(caminho))
        linha = extrair_linha_digitavel(texto)
        valor = None
        venc  = None

        if linha:
            c44 = linha_para_codigo44(linha)
            if c44:
                venc  = decodificar_vencimento(c44)
                valor = decodificar_valor(c44)

        if not venc:
            venc = extrair_vencimento_texto(texto)
        if not valor:
            valor = extrair_valor_texto(texto)

        return JSONResponse({
            "sucesso":         bool(linha),
            "simulado":        not OCR_ATIVO,
            "linha_digitavel": linha or "",
            "valor":           valor,
            "vencimento":      venc or "",
            "aviso": "" if linha else
                     "Código não encontrado. Tente foto mais nítida e bem iluminada.",
        })

    except Exception as e:
        raise HTTPException(500, f"Erro: {str(e)}")
    finally:
        if caminho.exists():
            os.remove(caminho)


@app.post("/api/boletos", status_code=201)
async def criar_boleto(dados: BoletoCreate):
    if not db:
        raise HTTPException(503, "Firebase não configurado.")
    if checar_duplicidade(dados.linha_digitavel):
        raise HTTPException(409, "⚠️ Boleto duplicado! Esta linha já está cadastrada.")

    linha_limpa = re.sub(r"[\s\.]", "", dados.linha_digitavel)
    venc_data   = datetime.strptime(dados.vencimento, "%d/%m/%Y")
    ids_criados = []

    for num in range(dados.parcela_atual, dados.total_parcelas + 1):
        doc = {
            "fornecedor":      dados.fornecedor,
            "loja_id":         dados.loja_id,
            "loja_nome":       dados.loja_nome,
            "cnpj_loja":       dados.cnpj_loja,
            "valor":           dados.valor,
            "vencimento":      venc_data.strftime("%d/%m/%Y"),
            "linha_digitavel": dados.linha_digitavel if num == dados.parcela_atual else "",
            "linha_limpa":     linha_limpa if num == dados.parcela_atual else "",
            "parcela":         f"{num}/{dados.total_parcelas}",
            "status":          "PENDENTE",
            "chave_nfe":       dados.chave_nfe or "",
            "data_emissao":    dados.data_emissao or "",
            "numero_nota":     dados.numero_nota or "",
            "data_criacao":    firestore.SERVER_TIMESTAMP,
        }
        _, ref = db.collection("boletos").add(doc)
        ids_criados.append(ref.id)
        venc_data += timedelta(days=30)

    return {
        "sucesso":     True,
        "ids_criados": ids_criados,
        "mensagem":    f"{len(ids_criados)} boleto(s) criado(s)."
    }


@app.get("/api/boletos")
async def listar_boletos(
    loja_id: Optional[str] = None,
    status:  Optional[str] = None
):
    if not db:
        return {"boletos": _demo()}
    try:
        q = db.collection("boletos")
        if loja_id:
            q = q.where("loja_id", "==", loja_id)
        if status:
            q = q.where("status", "==", status.upper())
        q = q.order_by("vencimento", direction=firestore.Query.ASCENDING)

        boletos = []
        for doc in q.get():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("linha_limpa", None)
            if d.get("data_criacao"):
                try:
                    d["data_criacao"] = d["data_criacao"].strftime("%d/%m/%Y %H:%M")
                except Exception:
                    d["data_criacao"] = ""
            boletos.append(d)
        return {"boletos": boletos}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/boletos/{boleto_id}/status")
async def atualizar_status(boleto_id: str, dados: StatusUpdate):
    if not db:
        raise HTTPException(503, "Firebase não configurado.")
    ref = db.collection("boletos").document(boleto_id)
    if not ref.get().exists:
        raise HTTPException(404, "Boleto não encontrado.")
    ref.update({"status": dados.status})
    return {"sucesso": True, "novo_status": dados.status}


@app.delete("/api/boletos/{boleto_id}")
async def deletar_boleto(boleto_id: str):
    if not db:
        raise HTTPException(503, "Firebase não configurado.")
    ref = db.collection("boletos").document(boleto_id)
    if not ref.get().exists:
        raise HTTPException(404, "Boleto não encontrado.")
    ref.delete()
    return {"sucesso": True}


def _demo():
    hoje = datetime.now()
    return [
        {
            "id": "demo-1",
            "fornecedor": "SAO SALVADOR ALIMENTOS SA",
            "loja_id": "loja1", "loja_nome": "Loja 1 (Matriz)",
            "cnpj_loja": "37.319.385/0001-64", "valor": 1381.84,
            "vencimento": hoje.strftime("%d/%m/%Y"),
            "linha_digitavel": "00190.00009 03536.970209 02097.387175 2 14220000138184",
            "parcela": "1/1", "status": "PENDENTE"
        },
        {
            "id": "demo-2",
            "fornecedor": "TANAKA PROD COM E DIST",
            "loja_id": "loja1", "loja_nome": "Loja 1 (Matriz)",
            "cnpj_loja": "37.319.385/0001-64", "valor": 105.20,
            "vencimento": (hoje + timedelta(days=5)).strftime("%d/%m/%Y"),
            "linha_digitavel": "07090.00020 50444.410109 71187.070413 6 13920000010520",
            "parcela": "1/1", "status": "PENDENTE"
        },
    ]
