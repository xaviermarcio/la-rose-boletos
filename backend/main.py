"""
LA ROSE — backend/main.py
Servidor FastAPI com Firebase Admin, Auto-IP e todas as rotas da API.
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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from dotenv import load_dotenv

load_dotenv()

from ocr_engine import (
    processar_documento,
    extrair_linha_digitavel,
    extrair_valor,
    extrair_vencimento,
    ler_texto,
    OCR_ATIVO,
)

# Suporte a PDF
try:
    from pdf2image import convert_from_path
    PDF_ATIVO = True
except ImportError:
    PDF_ATIVO = False

import firebase_admin
from firebase_admin import credentials, firestore


# ── AUTO-IP ───────────────────────────────────────────────────────────────────

def descobrir_ip() -> str:
    """
    Detecta o IP da máquina na rede Wi-Fi local.
    Abre uma conexão UDP 'falsa' com o Google (8.8.8.8) sem
    enviar nada — só para descobrir qual interface de rede
    o sistema usaria, e portanto qual é o IP local.
    """
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
print(f"📡  IP local detectado: {IP}")
print(f"🌐  Acesse em: http://{IP}:{PORTA}")
print(f"🔬  OCR: {'Ativo' if OCR_ATIVO else 'Simulação'}")
print(f"📄  PDF: {'Ativo' if PDF_ATIVO else 'Instale pdf2image + Poppler'}\n")


# ── FIREBASE ──────────────────────────────────────────────────────────────────

def conectar_firebase() -> bool:
    """
    Conecta ao Firebase usando a chave de serviço JSON.
    O caminho da chave vem do arquivo .env via FIREBASE_KEY_PATH.
    Se o arquivo não existir, roda em modo demo sem salvar nada.
    """
    caminho = os.getenv("FIREBASE_KEY_PATH", "firebase-key.json")
    if os.path.exists(caminho):
        cred = credentials.Certificate(caminho)
        firebase_admin.initialize_app(cred)
        print(f"✅  Firebase conectado: {caminho}\n")
        return True
    print(f"⚠️   Chave Firebase não encontrada: {caminho}")
    print("     Rodando em modo demo — dados não serão salvos.\n")
    return False

FIREBASE_ATIVO = conectar_firebase()
db = firestore.client() if FIREBASE_ATIVO else None


# ── APP FASTAPI ───────────────────────────────────────────────────────────────

app = FastAPI(title="La Rose API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR     = Path(tempfile.gettempdir()) / "larose_temp"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
TEMP_DIR.mkdir(exist_ok=True)


# ── MODELOS DE DADOS ──────────────────────────────────────────────────────────

class BoletoCreate(BaseModel):
    """
    Define e valida os dados necessários para criar um boleto.
    O Pydantic rejeita automaticamente dados no formato errado.
    """
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
    """Valida a atualização de status de um boleto."""
    status: str

    @validator("status")
    def status_valido(cls, v):
        if v.upper() not in {"PENDENTE", "ENVIADO", "PAGO"}:
            raise ValueError("Status deve ser PENDENTE, ENVIADO ou PAGO")
        return v.upper()


# ── FUNÇÕES AUXILIARES ────────────────────────────────────────────────────────

def validar_linha(linha: str) -> bool:
    """Verifica se a linha digitável tem 47 ou 48 dígitos."""
    if not linha:
        return True
    limpa = re.sub(r"[\s\.]", "", linha)
    return bool(re.match(r"^\d{47,48}$", limpa))


def checar_duplicidade(linha: str) -> bool:
    """
    Consulta o Firestore para ver se esta linha digitável
    já foi cadastrada antes. Evita boleto pago em duplicidade.
    Retorna True se já existe (é duplicado).
    """
    if not db or not linha.strip():
        return False
    limpa = re.sub(r"[\s\.]", "", linha)
    docs  = (
        db.collection("boletos")
          .where("linha_limpa", "==", limpa)
          .limit(1)
          .get()
    )
    return len(docs) > 0


# ── ROTAS — ARQUIVOS ESTÁTICOS ────────────────────────────────────────────────

@app.get("/")
async def raiz():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/app.js")
async def servir_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"))

@app.get("/manifest.json")
async def manifesto():
    return FileResponse(str(FRONTEND_DIR / "manifest.json"))

@app.get("/sw.js")
async def service_worker():
    conteudo = (FRONTEND_DIR / "sw.js").read_text(encoding="utf-8")
    return Response(
        content=conteudo,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )

@app.get("/icons/{nome}")
async def icone(nome: str):
    caminho = FRONTEND_DIR / "icons" / nome
    if not caminho.exists():
        raise HTTPException(404, "Ícone não encontrado")
    return FileResponse(str(caminho))


# ── ROTAS — API ───────────────────────────────────────────────────────────────

@app.get("/api/config")
async def config():
    """Retorna configurações do servidor para o frontend."""
    return {
        "ip":             IP,
        "porta":          PORTA,
        "ocr_ativo":      OCR_ATIVO,
        "firebase_ativo": FIREBASE_ATIVO,
        "pdf_ativo":      PDF_ATIVO,
    }


@app.post("/api/ocr")
async def processar_ocr(
    arquivo: UploadFile = File(...),
    tipo: str = "Boleto"
):
    """
    Recebe imagem, salva temporariamente, processa OCR
    e apaga o arquivo logo em seguida.
    """
    if not arquivo.content_type or not arquivo.content_type.startswith("image/"):
        raise HTTPException(400, "Apenas imagens PNG/JPG são aceitas.")

    ext     = Path(arquivo.filename or "img.jpg").suffix or ".jpg"
    caminho = TEMP_DIR / f"{uuid.uuid4()}{ext}"

    try:
        conteudo = await arquivo.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)
        resultado = processar_documento(str(caminho), tipo)
        return JSONResponse(resultado)
    except Exception as e:
        raise HTTPException(500, f"Erro no OCR: {str(e)}")
    finally:
        # O bloco finally sempre executa — garante limpeza mesmo com erro
        if caminho.exists():
            os.remove(caminho)
            print(f"🗑️  Temporário removido: {caminho.name}")


@app.post("/api/codigo-rapido")
async def codigo_rapido(arquivo: UploadFile = File(...)):
    """
    Fluxo expresso: recebe foto ou PDF de um boleto e retorna
    apenas a linha digitável, valor e vencimento.
    Não salva nada no banco — 100% expresso.
    """
    tipo_arquivo = arquivo.content_type or ""
    eh_pdf       = "pdf" in tipo_arquivo
    eh_imagem    = tipo_arquivo.startswith("image/")

    if not eh_pdf and not eh_imagem:
        raise HTTPException(400, "Envie uma imagem JPG/PNG ou um PDF.")

    if eh_pdf and not PDF_ATIVO:
        raise HTTPException(
            501,
            "Suporte a PDF não instalado. "
            "Rode: pip install pdf2image "
            "e instale o Poppler (veja README)."
        )

    ext     = ".pdf" if eh_pdf else (Path(arquivo.filename or "b.jpg").suffix or ".jpg")
    caminho = TEMP_DIR / f"{uuid.uuid4()}{ext}"
    gerados = [caminho]

    try:
        conteudo = await arquivo.read()
        with open(caminho, "wb") as f:
            f.write(conteudo)

        texto_total = ""

        if eh_pdf:
            # Converte cada página do PDF em imagem e roda OCR
            paginas = convert_from_path(str(caminho), dpi=200)
            for i, pagina in enumerate(paginas):
                img_path = TEMP_DIR / f"{uuid.uuid4()}_p{i}.jpg"
                gerados.append(img_path)
                pagina.save(str(img_path), "JPEG")
                texto_total += ler_texto(str(img_path)) + "\n"
        else:
            texto_total = ler_texto(str(caminho))

        linha      = extrair_linha_digitavel(texto_total)
        valor      = extrair_valor(texto_total)
        vencimento = extrair_vencimento(texto_total)

        # Modo simulação quando OCR não está disponível
        if not OCR_ATIVO:
            linha      = "23793.38128 60007.827136 94000.063305 8 92340000125000"
            valor      = 1250.00
            vencimento = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")

        return JSONResponse({
            "sucesso":         bool(linha),
            "simulado":        not OCR_ATIVO,
            "linha_digitavel": linha or "",
            "valor":           valor,
            "vencimento":      vencimento or "",
            "aviso": "" if linha else
                     "Código não encontrado. Tente uma foto com mais luz e sem sombras.",
        })

    except Exception as e:
        raise HTTPException(500, f"Erro ao processar: {str(e)}")
    finally:
        for arq in gerados:
            if Path(arq).exists():
                os.remove(arq)
                print(f"🗑️  Removido: {Path(arq).name}")


@app.post("/api/boletos", status_code=201)
async def criar_boleto(dados: BoletoCreate):
    """
    Cria um ou mais boletos no Firestore.
    Se total_parcelas > 1, cria N documentos com
    vencimentos incrementais de 30 dias cada.
    """
    if not db:
        raise HTTPException(503, "Firebase não configurado.")

    if not validar_linha(dados.linha_digitavel):
        raise HTTPException(422, "Linha digitável inválida (47 ou 48 dígitos).")

    if checar_duplicidade(dados.linha_digitavel):
        raise HTTPException(
            409,
            "⚠️ Boleto duplicado! Esta linha digitável já está cadastrada."
        )

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
            "data_criacao":    firestore.SERVER_TIMESTAMP,
        }
        _, ref = db.collection("boletos").add(doc)
        ids_criados.append(ref.id)
        venc_data += timedelta(days=30)

    return {
        "sucesso":     True,
        "ids_criados": ids_criados,
        "mensagem":    f"{len(ids_criados)} boleto(s) criado(s) com sucesso."
    }


@app.get("/api/boletos")
async def listar_boletos(
    loja_id: Optional[str] = None,
    status:  Optional[str] = None
):
    """
    Retorna todos os boletos ordenados por vencimento.
    Aceita filtros opcionais por loja e status via URL.
    Exemplo: /api/boletos?loja_id=loja1&status=PENDENTE
    """
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
    """
    Atualiza apenas o campo status de um boleto específico.
    PATCH atualiza só o que você manda, sem mexer no resto.
    """
    if not db:
        raise HTTPException(503, "Firebase não configurado.")
    ref = db.collection("boletos").document(boleto_id)
    if not ref.get().exists:
        raise HTTPException(404, "Boleto não encontrado.")
    ref.update({"status": dados.status})
    return {"sucesso": True, "novo_status": dados.status}


@app.delete("/api/boletos/{boleto_id}")
async def deletar_boleto(boleto_id: str):
    """Remove permanentemente um boleto do Firestore."""
    if not db:
        raise HTTPException(503, "Firebase não configurado.")
    ref = db.collection("boletos").document(boleto_id)
    if not ref.get().exists:
        raise HTTPException(404, "Boleto não encontrado.")
    ref.delete()
    return {"sucesso": True}


# ── DADOS DE DEMONSTRAÇÃO ─────────────────────────────────────────────────────

def _demo():
    """Retorna boletos fictícios quando Firebase não está configurado."""
    hoje = datetime.now()
    return [
        {
            "id": "demo-1",
            "fornecedor": "DISTRIBUIDORA FLORES LTDA",
            "loja_id": "loja1",
            "loja_nome": "Loja 1 (Matriz)",
            "cnpj_loja": "37.319.385/0001-64",
            "valor": 3480.00,
            "vencimento": hoje.strftime("%d/%m/%Y"),
            "linha_digitavel": "23793.38128 60007.827136 94000.063305 8 92340000348000",
            "parcela": "1/3",
            "status": "PENDENTE"
        },
        {
            "id": "demo-2",
            "fornecedor": "EMBALAGENS PREMIUM S/A",
            "loja_id": "loja2",
            "loja_nome": "Loja 2 (Filial)",
            "cnpj_loja": "37.319.385/0002-45",
            "valor": 1220.50,
            "vencimento": (hoje + timedelta(days=5)).strftime("%d/%m/%Y"),
            "linha_digitavel": "34191.75009 35000.000000 09004.950008 9 92870000122050",
            "parcela": "2/6",
            "status": "ENVIADO"
        },
        {
            "id": "demo-3",
            "fornecedor": "TÊXTEIS DO NORDESTE LTDA",
            "loja_id": "loja1",
            "loja_nome": "Loja 1 (Matriz)",
            "cnpj_loja": "37.319.385/0001-64",
            "valor": 5200.00,
            "vencimento": (hoje + timedelta(days=15)).strftime("%d/%m/%Y"),
            "linha_digitavel": "23793.38128 60007.827136 94000.063305 8 92870000520000",
            "parcela": "1/2",
            "status": "PAGO"
        },
    ]