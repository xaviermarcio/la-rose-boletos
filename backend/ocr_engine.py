"""
LA ROSE — backend/ocr_engine.py
Motor de visão computacional e extração de dados via OCR.
"""

import re
import os
from datetime import datetime, timedelta
from typing import Optional

try:
    import cv2
    import numpy as np
    import pytesseract
    OCR_ATIVO = True
except ImportError:
    OCR_ATIVO = False

# No Windows o Tesseract precisa do caminho completo informado
if os.name == "nt" and OCR_ATIVO:
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

# Tabela de lojas: CNPJ sem máscara → dados completos da loja
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


# ── ETAPA 1: MELHORA A IMAGEM ANTES DO OCR ───────────────────────────────────

def pre_processar(caminho: str):
    """
    Recebe o caminho de uma imagem e retorna uma versão
    melhorada para o OCR ler com mais precisão.

    Passo 1 → Escala de cinza: remove cores desnecessárias
    Passo 2 → CLAHE: melhora o contraste por regiões
    Passo 3 → Binarização: converte para preto e branco puro
    """
    img = cv2.imread(caminho)
    if img is None:
        raise ValueError(f"Não foi possível abrir: {caminho}")

    # Redimensiona se a imagem for muito grande (mantém proporção)
    h, w = img.shape[:2]
    if w > 2000:
        fator = 2000 / w
        img = cv2.resize(img, (2000, int(h * fator)))

    # Passo 1: converte de colorida (BGR) para escala de cinza
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Passo 2: CLAHE — melhora o contraste de forma inteligente
    # por regiões da imagem, não de forma global
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cinza = clahe.apply(cinza)

    # Passo 3: binarização adaptativa — preto e branco puro
    binarizado = cv2.adaptiveThreshold(
        cinza, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )
    return binarizado


# ── ETAPA 2: LEITURA OCR ─────────────────────────────────────────────────────

def ler_texto(caminho: str) -> str:
    """
    Roda o OCR na imagem pré-processada E na original.
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


# ── ETAPA 3: EXTRAÇÃO COM REGEX ──────────────────────────────────────────────

def extrair_chave_nfe(texto: str) -> Optional[str]:
    """
    Busca a chave de acesso da NFe de 44 dígitos.

    O problema comum é que o OCR às vezes quebra a chave em
    várias linhas ou insere espaços no meio. Por isso fazemos
    três tentativas em ordem de confiabilidade:

    Tentativa 1 → remove tudo que não é número e busca 44 dígitos
                  seguidos. Funciona quando a chave está limpa.

    Tentativa 2 → busca grupos de 4 dígitos separados por espaço,
                  como "3524 0637 3193 8500 0164...". Algumas NFes
                  imprimem a chave nesse formato visual.

    Tentativa 3 → busca a palavra "Chave" ou "CHAVE" no texto e
                  pega os números que vierem logo depois dela.
                  Útil quando o OCR lê o rótulo junto.
    """

    # Tentativa 1: remove não-dígitos e busca sequência de 44
    apenas_numeros = re.sub(r"\D", "", texto)
    match = re.search(r"\d{44}", apenas_numeros)
    if match:
        return match.group(0)

    # Tentativa 2: chave no formato visual com espaços a cada 4 dígitos
    # Exemplo: "3524 0637 3193 8500 0164 5500 1000 0123 4510 0012 3456"
    padrao_visual = re.search(
        r"(\d{4}[\s\-]){10}\d{4}", texto
    )
    if padrao_visual:
        chave = re.sub(r"\D", "", padrao_visual.group(0))
        if len(chave) == 44:
            return chave

    # Tentativa 3: procura o rótulo "Chave de Acesso" e pega os números seguintes
    padrao_rotulo = re.search(
        r"chave[^\d]{0,30}([\d\s]{44,55})",
        texto,
        re.IGNORECASE
    )
    if padrao_rotulo:
        chave = re.sub(r"\D", "", padrao_rotulo.group(1))
        if len(chave) == 44:
            return chave

    return None


def identificar_loja(chave: str) -> dict:
    """
    Identifica a loja buscando o CNPJ dentro da chave NFe.

    A chave de 44 dígitos tem estrutura fixa:
    Pos  1- 2 → código do estado (ex: 35 = SP)
    Pos  3- 8 → ano e mês de emissão (AAMM)
    Pos  9-22 → CNPJ do emitente ← É AQUI QUE CHECAMOS
    Pos 23-24 → modelo do documento
    Pos 25-27 → série
    ...e assim por diante até os 44 dígitos.

    Então basta verificar se o CNPJ da Loja 1 ou da Loja 2
    aparece em algum lugar dentro da chave.
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
    """
    Extrai a linha digitável do boleto.
    Tenta dois padrões: com pontos/espaços ou só números (47-48 dígitos).
    """
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
    """
    Extrai o valor monetário em reais.
    Tenta encontrar padrões como R$ 1.250,00
    """
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
    """
    Extrai a data de vencimento no formato DD/MM/AAAA.
    """
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
    """
    Tenta extrair o nome do fornecedor/cedente.
    """
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


# ── FUNÇÃO PRINCIPAL ─────────────────────────────────────────────────────────

def processar_documento(caminho: str, tipo: str) -> dict:
    """
    Orquestra tudo: imagem → OCR → extração → dicionário de dados.
    Retorna sempre um dicionário com sucesso, dados e se é simulado.
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
    """Dados de exemplo para quando o Tesseract não está instalado."""
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