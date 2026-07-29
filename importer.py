"""
importer.py — leitura e normalização das planilhas de origem
(aba ATIVOS = consumo, aba LEITURA = leitura de cocho).

Feito para tolerar pequenas variações: procura a aba certa pelo nome
(contém 'ATIVO' / 'LEITURA'), e se não encontrar usa a 1ª / 2ª aba.
Colunas que não existirem na planilha do usuário simplesmente ficam
em branco — não quebra a importação.
"""

import pandas as pd
import re
import io
import requests

from db import ATIVOS_COLS, LEITURA_COLS


def _norm_col(c):
    return re.sub(r"\s+", " ", str(c).strip())


def extrair_sheet_id(url_ou_id: str) -> str:
    """Aceita tanto o ID puro da planilha quanto a URL completa do Google Sheets."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_ou_id)
    if m:
        return m.group(1)
    return url_ou_id.strip()


def baixar_google_sheet(url_ou_id: str):
    """Baixa uma planilha do Google Sheets (compartilhada como 'Qualquer pessoa
    com o link pode visualizar') e devolve um arquivo em memória (.xlsx),
    pronto para passar direto pra read_ativos()/read_leitura()."""
    sheet_id = extrair_sheet_id(url_ou_id)
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    resp = requests.get(export_url, timeout=30)
    resp.raise_for_status()
    if resp.content[:200].lstrip()[:15].lower().startswith(b"<!doctype html") or b"<html" in resp.content[:300].lower():
        raise ValueError(
            "Não consegui baixar a planilha do Google Sheets. Confirme que o "
            "compartilhamento está como 'Qualquer pessoa com o link pode "
            "visualizar' (Compartilhar → Acesso geral)."
        )
    return io.BytesIO(resp.content)


def _find_ativos_sheet(sheets: dict):
    """Acha a aba de Consumo por conteúdo (não só pelo nome), pois o novo
    modelo de planilha (ex.: arquivos 'CDZ...') chama a aba de 'Planilha1'
    e não de 'ATIVOS'."""
    for name, df in sheets.items():
        cols_upper = [_norm_col(c).upper() for c in df.columns]
        tem_curral = "CURRAL" in cols_upper
        tem_consumo = any(c in cols_upper for c in ("CONSUMO_MS", "QTDMASSASECA"))
        if tem_curral and tem_consumo:
            return df
    for name in sheets:
        if "ATIVO" in name.upper():
            return sheets[name]
    names = list(sheets.keys())
    return sheets[names[0]]


def read_ativos(file) -> pd.DataFrame:
    """Lê o arquivo de consumo e devolve DataFrame com as colunas esperadas
    por db.ATIVOS_COLS (faltantes viram NaN). Entende tanto o modelo antigo
    (colunas em maiúsculo tipo 'DATA', 'CAB', 'CONSUMO_MS') quanto o novo
    modelo (colunas tipo 'Data', 'QtdAnimais', 'QtdMassaSeca', ex.: arquivos
    'CDZ...xlsx')."""
    sheets = pd.read_excel(file, sheet_name=None)
    raw = _find_ativos_sheet(sheets)
    raw.columns = [_norm_col(c) for c in raw.columns]
    colmap = {c.upper(): c for c in raw.columns}

    def col(*nomes):
        for n in nomes:
            chave = n.upper()
            if chave in colmap:
                return raw[colmap[chave]]
        return pd.Series([None] * len(raw))

    out = pd.DataFrame()
    out["DATA"] = pd.to_datetime(col("DATA", "Data"), errors="coerce")
    out["CURRAL"] = col("CURRAL", "Curral")
    out["LOTE"] = pd.to_numeric(col("LOTE", "Lote"), errors="coerce")
    out["CAB"] = pd.to_numeric(col("CAB", "QtdAnimais"), errors="coerce")
    out["RACA"] = col("RACA", "Raça", "Raca")
    out["REBANHO_NOME"] = col("REBANHO_NOME", "NomeRebanho")
    out["CATEGORIA_NOME"] = col("CATEGORIA_NOME", "Categoria")
    out["DATA_ENTRADA"] = pd.to_datetime(col("DATA_ENTRADA", "DataEntrada"), errors="coerce")
    out["DIAS_CONF"] = pd.to_numeric(col("DIAS_CONF", "DiasConfinamento"), errors="coerce")
    out["PESO_ENTRADA"] = pd.to_numeric(col("PESO_ENTRADA", "PesoEntrada"), errors="coerce")
    out["PESO_MEDIO_ATUAL"] = pd.to_numeric(col("PESO_MEDIO_ATUAL", "PesoProjetado"), errors="coerce")
    out["RACAO_ATUAL"] = col("RACAO_ATUAL", "NomeRacao")
    out["TIPO_RACAO_ATUAL"] = col("TIPO_RACAO_ATUAL", "TipoRacao")
    out["TIPO_DIAS_RACAO"] = pd.to_numeric(col("TIPO_DIAS_RACAO", "DiasRacaoTipo"), errors="coerce")
    out["GMD_MEDIO"] = pd.to_numeric(col("GMD_MEDIO", "GMD"), errors="coerce")
    out["CONSUMO_MS"] = pd.to_numeric(col("CONSUMO_MS", "QtdMassaSeca"), errors="coerce")
    out["CONSUMO_MN"] = pd.to_numeric(col("CONSUMO_MN", "QtdMassaNatural"), errors="coerce")
    out["IMS_PV_DODIA"] = pd.to_numeric(col("IMS_PV_DODIA", "IMSDia"), errors="coerce")
    out["AJUSTE_KG_1"] = pd.to_numeric(col("AJUSTE KG 1", "AjusteKg1"), errors="coerce")
    out["AJUSTE_KG_2"] = pd.to_numeric(col("AJUSTE KG 2", "AjusteKg2"), errors="coerce")
    out["AJUSTE_KG_3"] = pd.to_numeric(col("AJUSTE KG 3", "AjusteKg3"), errors="coerce")
    out["LEITURA1"] = pd.to_numeric(col("LEITURA1", "NotaLeituraCocho"), errors="coerce")
    out["LEITURA2"] = pd.to_numeric(col("LEITURA2", "NotaLeituraCocho2"), errors="coerce")
    out["LEITURA3"] = pd.to_numeric(col("LEITURA3", "NotaLeituraCocho3"), errors="coerce")

    out = out.dropna(subset=["DATA", "CURRAL", "LOTE"])
    out["LOTE"] = out["LOTE"].astype(int)
    return out[ATIVOS_COLS]


def _find_leitura_sheet(sheets: dict):
    """Acha a aba de Leitura de Cocho por conteúdo (não só pelo nome), pois o
    novo modelo de planilha chama a aba de 'Página1' e não de 'LEITURA'."""
    for name, df in sheets.items():
        cols_upper = [_norm_col(c).upper() for c in df.columns]
        tem_curral = "CURRAL" in cols_upper
        tem_hora = any(h in cols_upper for h in ("06 HORAS", "06H", "20 HORAS", "20H"))
        if tem_curral and tem_hora:
            return df
    # fallback: nome contendo LEITURA, senão a 2ª aba, senão a 1ª
    for name in sheets:
        if "LEITURA" in name.upper():
            return sheets[name]
    names = list(sheets.keys())
    return sheets[names[1]] if len(names) > 1 else sheets[names[0]]


# códigos abreviados usados no novo modelo de planilha -> nomes usados no app
_MAPA_06H = {"D": "Dry", "I": "Inventory", "C": "Crumbs"}


def _normaliza_06h(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return v
    s = str(v).strip()
    return _MAPA_06H.get(s.upper(), s)


def read_leitura(file) -> pd.DataFrame:
    """Lê o arquivo de leitura de cocho. Entende tanto o modelo antigo
    (aba 'LEITURA', colunas '20 horas', '06 horas' com 'Dry'/'Crumbs'/'Inventory')
    quanto o novo modelo (aba 'Página1', colunas '20h', '06h' com 'D'/'C'/'I').
    Colunas que não existirem na planilha do usuário (ex.: '18h', '16h') ficam
    em branco — não quebra a importação."""
    sheets = pd.read_excel(file, sheet_name=None)
    raw = _find_leitura_sheet(sheets)
    raw.columns = [_norm_col(c) for c in raw.columns]
    colmap = {c.upper(): c for c in raw.columns}

    def col(*nomes):
        for n in nomes:
            chave = n.upper()
            if chave in colmap:
                return raw[colmap[chave]]
        return pd.Series([None] * len(raw))

    out = pd.DataFrame()
    out["DATA"] = pd.to_datetime(col("DATA DIURNA", "DATA"), errors="coerce")
    out["CURRAL"] = col("CURRAL")
    out["H18"] = col("18 HORAS", "18H")
    out["H20"] = col("20 HORAS", "20H")
    out["H00"] = col("00 HORAS", "00H")
    out["H03"] = col("03 HORAS", "03H")
    out["H06"] = col("06 HORAS", "06H").apply(_normaliza_06h)
    out["SOBRA"] = pd.to_numeric(col("SOBRA (KG)", "SOBRAS", "SOBRA"), errors="coerce")
    out["H12"] = col("12 HORAS", "12H")
    out["H16"] = col("16 HORAS", "16H")

    out = out.dropna(subset=["DATA", "CURRAL"])
    return out[LEITURA_COLS]
