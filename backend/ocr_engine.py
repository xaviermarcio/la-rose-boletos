"""
LA ROSE — backend/ocr_engine.py
Motor de visão computacional e extração de dados via OCR.
"""

import re
import os
from datetime import datetime, timedelta
from typing import Optional

# ── Tenta importar as libs de OCR ─────────────────────────────────────────────
try:
    import cv2
    import numpy as np
    import pytesseract
    _LIBS_OK = True
except ImportError:
    _LIBS_OK = False

# ── Localiza o Tesseract no Windows ───────────────────────────────────────────
# Tenta os caminhos mais comuns de instalação.
# Se não encontrar nenhum, o sistema roda em modo simulação.
OCR_ATIVO = False

if _LIBS_OK:
    if os.name == "nt":  # Windows
        caminhos_possiveis = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\xavie\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            r"C:\tools\Tesseract-OCR\tesseract.exe",
        ]
        for caminho in caminhos_possiveis:
            if os.path.exists(caminho):
                pytesseract.pytesseract.tesseract_cmd = caminho
                OCR_ATIVO = True
                print(f"✅  Tesseract encontrado: {caminho}")
                break
        if not OCR_ATIVO:
            print("⚠️   Tesseract não encontrado nos caminhos conhecidos.")
            print("     Rodando em modo simulação.")
            print("     Para instalar: https://github.com/UB-Mannheim/tesseract/wiki")
    else:
        # Linux / macOS — Tesseract fica no PATH automaticamente
        OCR_ATIVO = True


# ── CNPJ das lojas ────────────────────────────────────────────────────────────
LOJAS = {
    "37319385000164": {
        "loja_id":   "loja1",
        "loja_nome": "Loja 1 (Matriz)",
        "cnpj":      "37.319.385/0001-64"
    },
    "37319385000245": {
        "loja_id":   "loja2",
        "loja_nome": "Loja 2 (Filial)",
        "cnpj":      "37.319.385/0002-45"
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  PRÉ-PROCESSAMENTO DE IMAGEM
# ══════════════════════════════════════════════════════════════════════════════

def pre_processar(caminho: str):
    """
    Melhora a imagem antes do OCR.
    Escala de cinza → CLAHE → binarização adaptativa.
    """
    img = cv2.imread(caminho)
    if img is None:
        raise ValueError(f"Não foi possível abrir a imagem: {caminho}")

    h, w = img.shape[:2]
    if w > 2000:
        fator = 2000 / w
        img = cv2.resize(img, (2000, int(h * fator)))

    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cinza = clahe.apply(cinza)

    binarizado = cv2.adaptiveThreshold(
        cinza, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )
    return binarizado


# ══════════════════════════════════════════════════════════════════════════════
#  LEITURA OCR
# ══════════════════════════════════════════════════════════════════════════════

def ler_texto(caminho: str) -> str:
    """
    Roda OCR na imagem pré-processada e na original.
    Combina os dois resultados para maximizar a precisão.
    """
    if not OCR_ATIVO:
        return ""

    config = r"--oem 3 --psm 6 -l por+eng"

    img_proc   = pre_processar(caminho)
    texto_proc = pytesseract.image_to_string(img_proc, config=config)

    img_orig   = cv2.imread(caminho)
    texto_orig = pytesseract.image_to_string(img_orig, config=config)

    return texto_proc + "\n" + texto_orig


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRAÇÃO COM REGEX
# ══════════════════════════════════════════════════════════════════════════════

def extrair_chave_nfe(texto: str) -> Optional[str]:
    """
    Busca a chave de acesso de 44 dígitos da NFe.
    Tenta três estratégias em ordem de confiabilidade.
    """
    # Tentativa 1: remove não-dígitos e busca 44 consecutivos
    apenas_numeros = re.sub(r"\D", "", texto)
    match = re.search(r"\d{44}", apenas_numeros)
    if match:
        return match.group(0)

    # Tentativa 2: chave no formato visual com espaços a cada 4 dígitos
    padrao_visual = re.search(r"(\d{4}[\s\-]){10}\d{4}", texto)
    if padrao_visual:
        chave = re.sub(r"\D", "", padrao_visual.group(0))
        if len(chave) == 44:
            return chave

    # Tentativa 3: busca o rótulo "Chave" e pega os números seguintes
    padrao_rotulo = re.search(
        r"chave[^\d]{0,30}([\d\s]{44,55})",
        texto, re.IGNORECASE
    )
    if padrao_rotulo:
        chave = re.sub(r"\D", "", padrao_rotulo.group(1))
        if len(chave) == 44:
            return chave

    return None


def identificar_loja(chave: str) -> dict:
    """
    Identifica a loja buscando o CNPJ embutido na chave NFe.
    O CNPJ fica nas posições 9 a 22 da chave de 44 dígitos.
    """
    for cnpj, dados in LOJAS.items():
        if cnpj in chave:
            return dados
    return {
        "loja_id":   "desconhecida",
        "loja_nome": "Não Identificada",
        "cnpj":      ""
    }


def extrair_linha_digitavel(texto: str) -> Optional[str]:
    """Extrai linha digitável do boleto (47 ou 48 dígitos)."""
    padroes = [
        r"\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}",
        r"\d{47,48}",
    ]
    for p in padroes:
        match = re.search(p, texto)
        if match:
            return match.group(0).strip()
    return None


def extrair_valor(texto: str) -> Optional[float]:
    """Extrai valor monetário em reais."""
    padroes = [
        r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
        r"VALOR[:\s]+R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
        r"(\d{1,3}(?:\.\d{3})*,\d{2})",
    ]
    for p in padroes:
        resultados = re.findall(p, texto, re.IGNORECASE)
        if resultados:
            try:
                return float(
                    resultados[0].replace(".", "").replace(",", ".")
                )
            except ValueError:
                continue
    return None


def extrair_vencimento(texto: str) -> Optional[str]:
    """Extrai data de vencimento no formato DD/MM/AAAA."""
    padroes = [
        r"VENCIMENTO[:\s]+(\d{2}/\d{2}/\d{4})",
        r"VENC\.?[:\s]+(\d{2}/\d{2}/\d{4})",
        r"(\d{2}/\d{2}/\d{4})",
    ]
    for p in padroes:
        match = re.search(p, texto, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extrair_fornecedor(texto: str) -> Optional[str]:
    """Tenta extrair o nome do fornecedor/cedente."""
    padroes = [
        r"CEDENTE[:\s]+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^\n]{3,60})",
        r"BENEFICI[ÁA]RIO[:\s]+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^\n]{3,60})",
        r"FAVORECIDO[:\s]+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^\n]{3,60})",
    ]
    for p in padroes:
        match = re.search(p, texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:80]
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  FUNÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def processar_documento(caminho: str, tipo: str) -> dict:
    """
    Orquestra todo o processo:
    imagem → OCR → extração → dicionário de dados estruturados.
    """
    resultado = {
        "tipo":     tipo,
        "sucesso":  False,
        "simulado": False,
        "dados":    {}
    }

    if not OCR_ATIVO:
        resultado["simulado"] = True
        resultado["sucesso"]  = True
        resultado["dados"]    = _dados_simulados(tipo)
        return resultado

    texto = ler_texto(caminho)

    if tipo == "NFe":
        chave = extrair_chave_nfe(texto)
        if chave:
            loja = identificar_loja(chave)
            resultado["sucesso"] = True
            resultado["dados"]   = {
                "chave_nfe":  chave,
                "loja_id":    loja["loja_id"],
                "loja_nome":  loja["loja_nome"],
                "cnpj_loja":  loja["cnpj"],
                "fornecedor": extrair_fornecedor(texto) or "",
                "valor":      extrair_valor(texto),
                "vencimento": extrair_vencimento(texto) or "",
            }
        else:
            # NFe processada mas chave não encontrada
            resultado["sucesso"] = False
            resultado["dados"]   = {
                "chave_nfe":  "",
                "loja_id":    "loja1",
                "loja_nome":  "Loja 1 (Matriz)",
                "cnpj_loja":  "37.319.385/0001-64",
                "fornecedor": extrair_fornecedor(texto) or "",
                "valor":      extrair_valor(texto),
                "vencimento": extrair_vencimento(texto) or "",
            }

    elif tipo == "Boleto":
        linha = extrair_linha_digitavel(texto)
        valor = extrair_valor(texto)
        venc  = extrair_vencimento(texto)
        resultado["sucesso"] = bool(linha or valor)
        resultado["dados"]   = {
            "linha_digitavel": linha or "",
            "valor":           valor,
            "vencimento":      venc or "",
            "fornecedor":      extrair_fornecedor(texto) or "",
        }

    return resultado


def _dados_simulados(tipo: str) -> dict:
    """Dados de exemplo quando Tesseract não está disponível."""
    venc = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
    if tipo == "NFe":
        return {
            "chave_nfe":  "35240637319385000164550010000123451000123456",
            "loja_id":    "loja1",
            "loja_nome":  "Loja 1 (Matriz)",
            "cnpj_loja":  "37.319.385/0001-64",
            "fornecedor": "DISTRIBUIDORA EXEMPLO LTDA",
            "valor":      1250.00,
            "vencimento": venc,
        }
    return {
        "linha_digitavel": "23793.38128 60007.827136 94000.063305 8 92340000125000",
        "valor":           1250.00,
        "vencimento":      venc,
        "fornecedor":      "DISTRIBUIDORA EXEMPLO LTDA",
    }