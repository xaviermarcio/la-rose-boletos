"""
LA ROSE — backend/ocr_engine.py

Pipeline de leitura em 3 camadas:
  1. PDF digital  -> pdfplumber (texto nativo, 100% precisao, sem OCR)
  2. Imagem JPG/PNG -> Tesseract + OpenCV (4 estrategias de pre-processamento)
  3. Validacao    -> modulo 10 detecta e corrige erros de OCR automaticamente
"""

import re
import os
from datetime import datetime, timedelta
from typing import Optional

# Libs de visao
try:
    import cv2
    import numpy as np
    import pytesseract
    _LIBS_OK = True
except ImportError:
    _LIBS_OK = False

# pdfplumber
try:
    import pdfplumber
    _PDF_OK = True
except ImportError:
    _PDF_OK = False
    print("AVISO: pdfplumber nao instalado. Rode: pip install pdfplumber")

# Tesseract
OCR_ATIVO = False
if _LIBS_OK:
    if os.name == "nt":
        caminhos = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\xavie\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            r"C:\tools\Tesseract-OCR\tesseract.exe",
        ]
        for c in caminhos:
            if os.path.exists(c):
                pytesseract.pytesseract.tesseract_cmd = c
                OCR_ATIVO = True
                print(f"Tesseract: {c}")
                break
        if not OCR_ATIVO:
            print("Tesseract nao encontrado - modo simulacao.")
    else:
        OCR_ATIVO = True

LANGS = "por+eng"
if OCR_ATIVO:
    try:
        langs = pytesseract.get_languages()
        LANGS = "por+eng" if "por" in langs else "eng"
        print(f"OCR idioma: {LANGS}")
    except Exception:
        LANGS = "por+eng"

LOJAS = {
    "37319385000164": {"loja_id": "loja1", "loja_nome": "Loja 1 (Matriz)", "cnpj": "37.319.385/0001-64"},
    "37319385000245": {"loja_id": "loja2", "loja_nome": "Loja 2 (Filial)",  "cnpj": "37.319.385/0002-45"},
}


# =============================================================================
#  MODULO 10 - VALIDACAO E AUTOCORRECAO
# =============================================================================

def _mod10(numero: str) -> int:
    soma, mult = 0, 2
    for d in reversed(numero):
        r = int(d) * mult
        soma += r // 10 + r % 10
        mult = 1 if mult == 2 else 2
    return (10 - soma % 10) % 10


def validar_linha(linha: str) -> bool:
    dig = re.sub(r"\D", "", linha)
    if len(dig) != 47:
        return False
    return (_mod10(dig[:9])    == int(dig[9])  and
            _mod10(dig[10:20]) == int(dig[20]) and
            _mod10(dig[21:31]) == int(dig[31]))


def tentar_corrigir_linha(linha: str) -> Optional[str]:
    """Tenta corrigir erros de OCR nos digitos verificadores."""
    dig = re.sub(r"\D", "", linha)
    if len(dig) != 47:
        return None
    if validar_linha(dig):
        return _fmt(dig)
    confusoes = {"0": "8", "8": "0", "1": "7", "7": "1",
                 "5": "6", "6": "5", "3": "8", "9": "4"}
    for pos in [9, 20, 31]:
        d_orig = dig[pos]
        for d_alt in confusoes.get(d_orig, ""):
            t = dig[:pos] + d_alt + dig[pos+1:]
            if validar_linha(t):
                print(f"DV corrigido pos {pos}: {d_orig}->{d_alt}")
                return _fmt(t)
    return None


def _fmt(dig: str) -> str:
    return (f"{dig[0:5]}.{dig[5:10]} {dig[10:15]}.{dig[15:21]} "
            f"{dig[21:26]}.{dig[26:32]} {dig[32]} {dig[33:47]}")


# =============================================================================
#  CAMADA 1 - PDF NATIVO (pdfplumber)
# =============================================================================

def ler_pdf_nativo(caminho: str) -> str:
    if not _PDF_OK:
        return ""
    try:
        texto = ""
        with pdfplumber.open(caminho) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
        if len(re.sub(r"\s", "", texto)) > 50:
            print(f"PDF nativo: {len(texto)} chars")
            return texto
        return ""
    except Exception as e:
        print(f"pdfplumber erro: {e}")
        return ""


def extrair_dados_pdf_boleto(texto: str) -> dict:
    """Extracao especializada para PDF de boleto."""
    dados = {"linha_digitavel": None, "vencimento": None, "valor": None, "fornecedor": None}

    # Linha digitavel
    padroes = re.findall(
        r"\d{5}[\.\s]\d{5}\s+\d{5}[\.\s]\d{6}\s+\d{5}[\.\s]\d{6}\s+\d\s+\d{14}", texto
    )
    if padroes:
        for l in padroes:
            if validar_linha(l):
                dados["linha_digitavel"] = l
                break
        if not dados["linha_digitavel"]:
            dados["linha_digitavel"] = padroes[0]

    # Vencimento + Valor na mesma linha (padrao de boleto bancario)
    for linha in texto.split("\n"):
        m = re.search(r"(\d{2}/\d{2}/\d{4})\s+R\$([\d\.]+,\d{2})", linha)
        if m:
            a = int(m.group(1).split("/")[2])
            if 2024 <= a <= 2030:
                vf = float(m.group(2).replace(".", "").replace(",", "."))
                if 10 <= vf <= 999999:
                    dados["vencimento"] = m.group(1)
                    dados["valor"]      = vf
                    break

    # Fallback vencimento
    if not dados["vencimento"]:
        m = re.search(r"(?:Vencimento|VENCIMENTO)\s+(\d{2}/\d{2}/\d{4})", texto)
        if m:
            dados["vencimento"] = m.group(1)

    # Fallback valor: menor valor valido no documento
    if not dados["valor"]:
        candidatos = []
        for v in re.findall(r"R\$([\d\.]+,\d{2})", texto):
            vf = float(v.replace(".", "").replace(",", "."))
            if 10 <= vf <= 999999:
                candidatos.append(vf)
        if candidatos:
            dados["valor"] = min(candidatos)

    # Fornecedor/Beneficiario
    linhas = texto.split("\n")
    for i, l in enumerate(linhas):
        if re.search(r"Benefici[aá]rio|BENEFICIARIO", l, re.IGNORECASE):
            if i + 1 < len(linhas):
                nome = re.sub(r"CPF/CNPJ.*", "", linhas[i+1]).strip()
                if 5 <= len(nome) <= 80:
                    dados["fornecedor"] = nome
                    break

    return dados


# =============================================================================
#  CAMADA 2 - OCR DE IMAGEM (Tesseract + OpenCV)
# =============================================================================

def corrigir_orientacao(img):
    try:
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        osd   = pytesseract.image_to_osd(cinza, config="--psm 0 -l osd")
        match = re.search(r"Rotate:\s*(\d+)", osd)
        if match:
            angulo = int(match.group(1))
            if angulo == 90:    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif angulo == 180: img = cv2.rotate(img, cv2.ROTATE_180)
            elif angulo == 270: img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    except Exception:
        pass
    return img


def redimensionar(img, largura=2000):
    h, w = img.shape[:2]
    if w < 800:
        fator = 1600 / w
        img = cv2.resize(img, (1600, int(h * fator)), interpolation=cv2.INTER_CUBIC)
        h, w = img.shape[:2]
    if w > largura:
        fator = largura / w
        img = cv2.resize(img, (largura, int(h * fator)), interpolation=cv2.INTER_AREA)
    return img


def ler_texto_imagem(caminho: str) -> str:
    if not OCR_ATIVO:
        return ""
    try:
        img = cv2.imread(caminho)
        if img is None:
            return ""
        img   = redimensionar(img)
        img   = corrigir_orientacao(img)
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cfg_d = f"--oem 3 --psm 6 -l {LANGS}"
        cfg_n = f"--oem 3 --psm 6 -l eng"
        textos = []
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        v1 = clahe.apply(cinza)
        _, v1b = cv2.threshold(v1, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        textos.append(pytesseract.image_to_string(v1b, config=cfg_d))
        textos.append(pytesseract.image_to_string(v1b, config=cfg_n))
        v2 = cv2.adaptiveThreshold(cv2.GaussianBlur(cinza,(3,3),0), 255,
             cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8)
        textos.append(pytesseract.image_to_string(v2, config=cfg_d))
        _, v3 = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        textos.append(pytesseract.image_to_string(v3, config=cfg_n))
        g = cv2.resize(cinza,(cinza.shape[1]*2,cinza.shape[0]*2),interpolation=cv2.INTER_CUBIC)
        v4 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(g)
        _, v4b = cv2.threshold(v4, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        textos.append(pytesseract.image_to_string(v4b, config=cfg_d))
        textos.append(pytesseract.image_to_string(v4b, config=cfg_n))
        return "\n".join(t for t in textos if t.strip())
    except Exception as e:
        print(f"Erro OCR: {e}")
        return ""


def ler_texto(caminho: str) -> str:
    from pathlib import Path as _P
    ext = _P(caminho).suffix.lower()
    if ext == ".pdf":
        t = ler_pdf_nativo(caminho)
        if t.strip():
            return t
        return ""
    return ler_texto_imagem(caminho)


# =============================================================================
#  EXTRACAO - BOLETO (imagem)
# =============================================================================

def extrair_linha_digitavel(texto: str) -> Optional[str]:
    p1 = re.search(r"\d{5}[\.\,]\d{5}\s+\d{5}[\.\,]\d{6}\s+\d{5}[\.\,]\d{6}\s+\d\s+\d{14}", texto)
    if p1: return p1.group(0).strip()
    p2 = re.search(r"\d{5}[\s\.\,\-]\d{5}\s+\d{5}[\s\.\,\-]\d{6}\s+\d{5}[\s\.\,\-]\d{6}\s+\d\s+\d{14}", texto)
    if p2: return p2.group(0).strip()
    for linha in texto.split("\n"):
        dig = re.sub(r"\D", "", linha)
        if len(dig) == 47: return _fmt(dig)
    m = re.search(r"\d{47}", re.sub(r"\D", "", texto))
    if m: return _fmt(m.group(0))
    return None


def linha_para_codigo44(linha: str) -> Optional[str]:
    try:
        dig = re.sub(r"\D", "", linha)
        if len(dig) == 44: return dig
        if len(dig) != 47: return None
        return dig[0:3]+dig[3]+dig[32]+dig[33:37]+dig[37:47]+dig[4:9]+dig[10:20]+dig[21:31]
    except Exception:
        return None


def decodificar_vencimento(codigo44: str) -> Optional[str]:
    try:
        fator = int(codigo44[5:9])
        if fator == 0: return None
        venc = datetime(1997, 10, 7) + timedelta(days=fator)
        if not (2020 <= venc.year <= 2035): return None
        return venc.strftime("%d/%m/%Y")
    except Exception:
        return None


def decodificar_valor(codigo44: str) -> Optional[float]:
    try:
        v = int(codigo44[9:19]) / 100.0
        return v if v > 0 else None
    except Exception:
        return None


def extrair_vencimento_texto(texto: str) -> Optional[str]:
    hoje = datetime.now()
    for p in [
        r"(?:VENCIMENTO|VENC\.?|DATA\s+(?:DE\s+)?VENC(?:IMENTO)?\.?)[:\s]+(\d{2}[\/\.\-]\d{2}[\/\.\-]\d{4})",
        r"(\d{2}/\d{2}/\d{4})\s+R\$",
    ]:
        for m in re.finditer(p, texto, re.IGNORECASE):
            ds = m.group(1)
            partes = re.sub(r"[\/\.\-]", "/", ds).split("/")
            try:
                d, mes, a = int(partes[0]), int(partes[1]), int(partes[2])
                if 1 <= d <= 31 and 1 <= mes <= 12 and 2020 <= a <= 2030:
                    return f"{partes[0]}/{partes[1]}/{partes[2]}"
            except Exception:
                continue
    futuros, passados = [], []
    for m in re.finditer(r"(\d{2}[\/\.]\d{2}[\/\.]\d{4})", texto):
        partes = re.sub(r"[\/\.\-]", "/", m.group(1)).split("/")
        try:
            d, mes, a = int(partes[0]), int(partes[1]), int(partes[2])
            if not (1 <= d <= 31 and 1 <= mes <= 12 and 2024 <= a <= 2030): continue
            diff = (datetime(a, mes, d) - hoje).days
            fmt  = f"{partes[0]}/{partes[1]}/{partes[2]}"
            if diff >= 0:      futuros.append((diff, fmt))
            elif diff >= -180: passados.append((abs(diff), fmt))
        except Exception:
            continue
    if futuros:  return min(futuros,  key=lambda x: x[0])[1]
    if passados: return min(passados, key=lambda x: x[0])[1]
    return None


def extrair_valor_texto(texto: str) -> Optional[float]:
    for p in [
        r"(?:VALOR\s+DO\s+DOCUMENTO|VALOR\s+COBRADO)[:\s]*R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
        r"R\$\s*(\d{1,3}\.\d{3},\d{2})",
        r"(\d{1,3}(?:\.\d{3})+,\d{2})",
    ]:
        for m in re.findall(p, texto, re.IGNORECASE):
            try:
                v = float(m.replace(".", "").replace(",", "."))
                if 10.0 <= v <= 999999.99:
                    return v
            except ValueError:
                continue
    return None


# =============================================================================
#  EXTRACAO - NFe
# =============================================================================

def extrair_chave_nfe(texto: str) -> Optional[str]:
    m = re.search(r"CHAVE\s+DE\s+ACESSO[^\d]{0,80}([\d\s]{47,60})", texto, re.IGNORECASE)
    if m:
        chave = re.sub(r"\D", "", m.group(1))[:44]
        if len(chave) == 44 and _uf_valida(chave): return chave
    for linha in texto.split("\n"):
        dig = re.sub(r"\D", "", linha)
        if len(dig) == 44 and _uf_valida(dig): return dig
    for m2 in re.finditer(r"\d{44}", re.sub(r"\D", "", texto)):
        if _uf_valida(m2.group(0)): return m2.group(0)
    blocos = re.findall(r"\b\d{4}\b", texto)
    for i in range(len(blocos) - 10):
        chave = "".join(blocos[i:i+11])
        if len(chave) == 44 and _uf_valida(chave): return chave
    return None


def _uf_valida(chave: str) -> bool:
    try: return 11 <= int(chave[:2]) <= 53
    except (ValueError, IndexError): return False


def identificar_loja(chave: str) -> dict:
    loja_padrao = {"loja_id": "loja1", "loja_nome": "Loja 1 (Matriz)", "cnpj": "37.319.385/0001-64"}
    if not chave: return loja_padrao
    for cnpj_num, dados in LOJAS.items():
        if cnpj_num in chave: return dados
    return {"loja_id": "desconhecida", "loja_nome": "Nao Identificada", "cnpj": ""}


def extrair_fornecedor_nfe(texto: str) -> Optional[str]:
    """
    Extrai o nome do emitente/fornecedor da NFe.
    Prioridade:
      1. Linha imediatamente após 'IDENTIFICACAO DO EMITENTE' (layout DANFE)
      2. Linha após 'EMITENTE' / 'RAZAO SOCIAL'
      3. Nome com sufixo juridico (SA, LTDA, etc.) no texto
    """
    linhas = texto.split("\n")

    # Fase 1: linha logo apos "IDENTIFICACAO DO EMITENTE"
    for i, l in enumerate(linhas):
        if re.search(r"IDENTIFICA[CÇ][AÃ]O\s+DO\s+EMITENTE", l, re.IGNORECASE):
            for j in range(i+1, min(i+4, len(linhas))):
                nome = linhas[j].strip()
                nome = re.sub(r"\s+", " ", nome)
                nome = re.sub(r"[|\\/_\[\]{}@#<>]", "", nome).strip()
                if len(nome) >= 3 and not re.match(r"^\d", nome):
                    return nome
            break

    # Fase 2: linha apos rotulos comuns
    for rotulo in [r"EMITENTE[:\s]", r"RAZ[AÃO]O\s+SOCIAL[:\s]", r"NOME\s+EMPRESARIAL[:\s]"]:
        m = re.search(rotulo + r"([^\n]{3,60})", texto, re.IGNORECASE)
        if m:
            nome = re.sub(r"\s+", " ", m.group(1).strip())
            if len(nome) >= 3:
                return nome

    # Fase 3: nome com sufixo juridico
    suffixes = r"(?:S\.?\s*A\.?|LTDA\.?|EIRELI|\bME\b|\bEPP\b|COMERCIO|INDUSTRIA|ALIMENTOS|DISTRIBUIDORA|ATACADO|AGRO|SUPERMERCADO)"
    candidatos = []
    for m in re.finditer(r"([A-Z][A-Z\s\.&]{2,50}" + suffixes + r"[\s\.]?)", texto, re.IGNORECASE):
        nome = re.sub(r"\s+", " ", m.group(1).strip())
        nome = re.sub(r"[|\\/_\[\]{}@#<>]", "", nome).strip()
        if 3 <= len(nome) <= 80:
            candidatos.append(nome)
    return max(candidatos, key=len) if candidatos else None


def extrair_data_emissao(texto: str) -> Optional[str]:
    hoje = datetime.now()
    candidatos = []
    for p in [
        r"(?:DATA\s+DA\s+EMISS.O|DATA\s+DE\s+EMISS.O)[:\s]+(\d{2}[\/\.\-]\d{2}[\/\.\-]\d{4})",
        r"(?:EMISS.O)[:\s]+(\d{2}[\/\.\-]\d{2}[\/\.\-]\d{4})",
        r"(\d{2}[\/\.]\d{2}[\/\.]\d{4})",
    ]:
        for m in re.finditer(p, texto, re.IGNORECASE):
            ds = m.group(1) if m.lastindex else m.group(0)
            partes = re.sub(r"[\/\.\-]", "/", ds).split("/")
            if len(partes) != 3: continue
            try:
                d, mes, a = int(partes[0]), int(partes[1]), int(partes[2])
                if not (1 <= d <= 31 and 1 <= mes <= 12 and 2020 <= a <= 2030): continue
                diff = abs((datetime(a, mes, d) - hoje).days)
                if diff <= 90: candidatos.append((diff, f"{partes[0]}/{partes[1]}/{partes[2]}"))
            except (ValueError, OverflowError): continue
    return min(candidatos, key=lambda x: x[0])[1] if candidatos else None


def extrair_numero_nota(texto: str) -> Optional[str]:
    """
    Extrai o numero da nota fiscal.
    Suporta: 'N° 000004522', 'N° 4522', 'Nº4522', 'NUMERO 4522'
    Remove zeros a esquerda: 000004522 -> 4522
    """
    padroes = [
        r"N[°o\.º]\s*(\d{3,9})",
        r"N[Uu][Mm][Ee][Rr][Oo]\s+(\d{3,9})",
        r"NOTA\s+FISCAL[^\d]{0,20}(\d{3,9})",
        r"NF[\-\s]?[eE]?\s*N[°o\.º]?\s*(\d{3,9})",
        r"\bN\.?(\d{6,9})\b",
    ]
    for p in padroes:
        m = re.search(p, texto, re.IGNORECASE)
        if m:
            num = m.group(1).lstrip("0")
            return num if num else "0"
    return None


# =============================================================================
#  FUNCAO PRINCIPAL
# =============================================================================

def processar_documento(caminho: str, tipo: str) -> dict:
    from pathlib import Path as _P
    resultado = {"tipo": tipo, "sucesso": False, "simulado": False,
                 "corrigido": False, "dados": {}}
    eh_pdf = _P(caminho).suffix.lower() == ".pdf"

    if eh_pdf:
        if not _PDF_OK:
            resultado.update({"simulado": True, "sucesso": True,
                              "dados": _dados_simulados(tipo),
                              "aviso": "Instale: pip install pdfplumber"})
            return resultado
        texto = ler_pdf_nativo(caminho)
        if not texto.strip():
            resultado.update({"sucesso": True, "simulado": True,
                              "dados": _dados_simulados(tipo),
                              "aviso": "PDF escaneado. Envie como JPG ou PNG."})
            return resultado
        if tipo == "Boleto":
            d = extrair_dados_pdf_boleto(texto)
            linha = d["linha_digitavel"]
            corrigido = False
            if linha and not validar_linha(linha):
                lc = tentar_corrigir_linha(linha)
                if lc: linha, corrigido = lc, True
            resultado.update({"sucesso": bool(linha or d["valor"]),
                              "corrigido": corrigido,
                              "dados": {"linha_digitavel": linha or "",
                                        "vencimento": d["vencimento"] or "",
                                        "valor": d["valor"],
                                        "fornecedor": d["fornecedor"] or ""}})
        elif tipo == "NFe":
            chave = extrair_chave_nfe(texto)
            loja  = identificar_loja(chave or "")
            resultado.update({"sucesso": True,
                              "dados": {"chave_nfe": chave or "",
                                        "loja_id":   loja["loja_id"],
                                        "loja_nome": loja["loja_nome"],
                                        "cnpj_loja": loja["cnpj"],
                                        "fornecedor":   extrair_fornecedor_nfe(texto) or "",
                                        "data_emissao": extrair_data_emissao(texto)   or "",
                                        "numero_nota":  extrair_numero_nota(texto)    or "",
                                        "valor": None, "vencimento": ""}})
        return resultado

    # Imagem
    if not OCR_ATIVO:
        resultado.update({"simulado": True, "sucesso": True, "dados": _dados_simulados(tipo)})
        return resultado
    texto = ler_texto_imagem(caminho)
    if not texto.strip():
        resultado.update({"simulado": True, "sucesso": True, "dados": _dados_simulados(tipo)})
        return resultado

    if tipo == "NFe":
        chave = extrair_chave_nfe(texto)
        loja  = identificar_loja(chave or "")
        resultado.update({"sucesso": True,
                          "dados": {"chave_nfe": chave or "",
                                    "loja_id":   loja["loja_id"],
                                    "loja_nome": loja["loja_nome"],
                                    "cnpj_loja": loja["cnpj"],
                                    "fornecedor":   extrair_fornecedor_nfe(texto) or "",
                                    "data_emissao": extrair_data_emissao(texto)   or "",
                                    "numero_nota":  extrair_numero_nota(texto)    or "",
                                    "valor": None, "vencimento": ""}})
    elif tipo == "Boleto":
        linha = extrair_linha_digitavel(texto)
        vencimento, valor, corrigido = None, None, False
        if linha:
            if not validar_linha(linha):
                lc = tentar_corrigir_linha(linha)
                if lc: linha, corrigido = lc, True
            c44 = linha_para_codigo44(linha)
            if c44:
                valor      = decodificar_valor(c44)
                vencimento = decodificar_vencimento(c44)
        if not vencimento: vencimento = extrair_vencimento_texto(texto)
        if not valor:      valor      = extrair_valor_texto(texto)
        resultado.update({"sucesso": bool(linha or valor), "corrigido": corrigido,
                          "dados": {"linha_digitavel": linha      or "",
                                    "vencimento":      vencimento or "",
                                    "valor":           valor,
                                    "fornecedor":      ""}})
    return resultado


def _dados_simulados(tipo: str) -> dict:
    venc = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
    hoje = datetime.now().strftime("%d/%m/%Y")
    if tipo == "NFe":
        return {"chave_nfe": "53260403387396009175500100283093713300773130",
                "loja_id": "loja1", "loja_nome": "Loja 1 (Matriz)",
                "cnpj_loja": "37.319.385/0001-64", "fornecedor": "SAO SALVADOR ALIMENTOS SA",
                "data_emissao": hoje, "numero_nota": "002830937", "valor": None, "vencimento": ""}
    return {"linha_digitavel": "00190.00009 03536.970209 02097.387175 2 14220000138184",
            "vencimento": venc, "valor": 1381.84, "fornecedor": ""}
