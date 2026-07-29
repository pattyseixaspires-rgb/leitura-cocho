"""
Manejo de Cocho — aplicativo Streamlit
Importa as planilhas de Ativos (consumo) e Leitura (cocho), acumula o
histórico em SQLite e mostra o painel por Curral/Lote.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import io
import re

import db
import importer


def _natural_key(s):
    """Chave de ordenação natural: entende 'C-1' < 'C-2' < ... < 'C-10' < 'C-14',
    e também lida com nomes que às vezes vêm com hífen e às vezes sem
    (ex.: 'A-9' e 'A10' no mesmo arquivo) — separa letras do número
    ignorando hífen/espaço no meio."""
    s = str(s)
    m = re.match(r"^([A-Za-z]+)[\s\-]*(\d+)(.*)$", s)
    if m:
        prefixo, numero, resto = m.groups()
        return (prefixo.upper(), int(numero), resto.upper())
    return (s.upper(), -1, "")

# ---------------------------------------------------------------------------
# Config / CSS
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Manejo de Cocho", page_icon="🐂", layout="wide")

TEAL_DARK = "#0B5E59"
TEAL = "#12847C"
ORANGE = "#F5A623"
GREEN = "#3FA34D"
YELLOW = "#F2C94C"
RED = "#E74C3C"
TAN = "#C9A876"
CYAN = "#4FB8B3"
BG = "#F3F6F6"

st.markdown(f"""
<style>
.stApp {{ background-color: {BG}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}

.header-banner {{
    background: linear-gradient(90deg, {TEAL_DARK} 0%, {TEAL} 100%);
    color: white; padding: 18px 26px; border-radius: 14px;
    margin-bottom: 14px; display:flex; align-items:center; justify-content:space-between;
}}
.header-banner h1 {{ margin:0; font-size:38px; }}
.header-banner span {{ opacity:0.92; font-size:20px; font-weight:600; }}

.st-key-header_container {{
    background: linear-gradient(90deg, {TEAL_DARK} 0%, {TEAL} 100%) !important;
    padding: 12px 22px 18px 22px; border-radius: 14px; margin-bottom: 10px;
}}
.header-title-wrap h1 {{ margin:0; font-size:46px; color:white; }}
.header-title-wrap span {{ opacity:0.95; font-size:30px; font-weight:800; color:white; }}

.metric-card {{
    background:white; border-radius:10px; padding:14px 12px; text-align:center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-top:4px solid {TEAL};
}}
.metric-card .label {{ font-size:17px; color:#607070; text-transform:uppercase; letter-spacing:.02em; font-weight:700;}}
.metric-card .value {{ font-size:36px; font-weight:800; color:{TEAL_DARK}; }}
.metric-card .value.small {{ font-size:20px; font-weight:700; white-space:normal; line-height:1.25; }}

.decisao-box {{
    background:white; border-radius:12px; padding:18px; margin-bottom:12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left:6px solid {TEAL};
}}
.decisao-title {{ font-weight:800; color:{TEAL_DARK}; font-size:22px; margin-bottom:4px;}}

.st-key-decisao_container {{
    background: linear-gradient(135deg, {TEAL_DARK} 0%, {TEAL} 100%) !important;
    border-radius:16px; padding:18px 20px 14px 20px; margin-bottom:14px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.18);
}}
.st-key-decisao_container label p {{ color:white !important; font-size:22px !important; font-weight:800 !important; }}
.st-key-decisao_container input {{
    font-size:38px !important; font-weight:800 !important; text-align:center !important;
    background:white !important; border-radius:10px !important; height:2.6em !important;
}}
.decisao-big-title {{ font-size:28px; font-weight:800; letter-spacing:.02em; margin-bottom:6px; color:white; }}
.decisao-preview {{ font-size:20px; opacity:0.95; margin-top:4px; color:white; font-weight:700; }}

.block-container h3 {{ margin-top: 0.2rem; margin-bottom: 0.4rem; font-size: 26px !important; }}
div[data-testid="stVerticalBlock"] {{ gap: 0.5rem; }}

.tbl-wrap {{ overflow-x:auto; background:white; border-radius:12px; padding:8px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }}
table.cocho {{ border-collapse:separate; border-spacing:0; font-size:20px; width:100%; table-layout:auto; font-weight:700; }}
table.cocho th, table.cocho td {{ padding:10px 12px; text-align:center; white-space:nowrap; border-bottom:1px solid #eef2f2; font-weight:800; background-clip:padding-box; }}
table.cocho th {{ background:{TEAL_DARK}; color:white; position:sticky; top:0; font-size:17px; font-weight:800; z-index:1; }}
table.cocho td.rowlabel, table.cocho th.rowlabel {{
    position:sticky; left:0; background:#eaf3f2; text-align:left; font-weight:800; color:{TEAL_DARK};
    z-index:2; font-size:18px; padding-right:12px; box-shadow: 2px 0 4px rgba(0,0,0,0.12);
}}
table.cocho th.rowlabel {{ background:{TEAL_DARK}; color:white; z-index:4;}}

.occ-count {{ display:inline-block; min-width:26px; padding:4px 10px; border-radius:12px; font-weight:800; font-size:16px; }}
.occ-zero {{ color:#bbb; }}
.occ-some {{ background:{ORANGE}; color:white; }}

.st-key-setas_container button {{
    background: white !important;
    border: 3px solid #F5A623 !important;
    color: {TEAL_DARK} !important;
    font-size: 20px !important;
    font-weight: 900 !important;
}}

.stButton button, .stDownloadButton button {{
    font-size: 19px !important;
    font-weight: 800 !important;
    padding-top: 0.6rem !important;
    padding-bottom: 0.6rem !important;
}}
button[kind="secondary"] {{ color: #111 !important; }}
button[kind="secondary"] p {{ color: #111 !important; font-weight: 800 !important; }}
button[kind="primary"] p {{ font-weight: 800 !important; }}

.badge {{ display:inline-block; min-width:30px; padding:5px 8px; border-radius:6px; font-weight:800; color:white; font-size:17px; }}

/* --- Barra lateral: aumenta tudo (títulos, botões, textos, rótulos) --- */
section[data-testid="stSidebar"] h2 {{ font-size: 26px !important; font-weight: 800 !important; }}
section[data-testid="stSidebar"] h3 {{ font-size: 22px !important; font-weight: 800 !important; }}
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div {{
    font-size: 18px !important;
}}
section[data-testid="stSidebar"] .stButton button,
section[data-testid="stSidebar"] .stDownloadButton button {{
    font-size: 20px !important;
    font-weight: 800 !important;
    padding-top: 0.7rem !important;
    padding-bottom: 0.7rem !important;
}}
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * ,
section[data-testid="stSidebar"] .stDateInput input,
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stCheckbox label p {{
    font-size: 18px !important;
    font-weight: 700 !important;
}}
section[data-testid="stSidebar"] small {{ font-size: 15px !important; }}
.b-s {{ background:{GREEN}; }}
.b-n {{ background:{YELLOW}; color:#453800;}}
.b-dry {{ background:{TAN}; color:#3a2e12;}}
.b-crumbs {{ background:{CYAN}; }}
.b-inv {{ background:{RED}; }}
.b-dash {{ color:#bbb; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Senha de acesso (compartilhada pela equipe)
# ---------------------------------------------------------------------------

def _checar_senha() -> bool:
    senha_configurada = None
    try:
        senha_configurada = st.secrets.get("APP_PASSWORD")
    except Exception:
        senha_configurada = None

    if not senha_configurada:
        # Sem senha configurada em secrets.toml: a tela de login fica desligada.
        return True

    if st.session_state.get("autenticado"):
        return True

    def _validar():
        if st.session_state.get("senha_digitada") == senha_configurada:
            st.session_state["autenticado"] = True
        else:
            st.session_state["autenticado"] = False

    st.markdown(
        f'<div class="header-title-wrap" style="background:{TEAL_DARK}; padding:24px; '
        f'border-radius:14px; max-width:420px; margin:60px auto 20px auto; text-align:center;">'
        f'<h1 style="font-size:28px;">🐂 Manejo de Cocho</h1>'
        f'<span style="font-size:16px;">Acesso restrito à equipe</span></div>',
        unsafe_allow_html=True,
    )
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_b:
        st.text_input("Senha de acesso", type="password", key="senha_digitada", on_change=_validar)
        if st.session_state.get("autenticado") is False:
            st.error("Senha incorreta. Tente de novo.")
    return False


if not _checar_senha():
    st.stop()

db.init_db()

# ---------------------------------------------------------------------------
# Sidebar — importação
# ---------------------------------------------------------------------------

st.sidebar.markdown("## 🐂 Manejo de Cocho")
st.sidebar.markdown("### 📥 Importar planilhas do dia")

up_ativos = st.sidebar.file_uploader("Planilha de Consumo (aba Ativos)", type=["xlsx"], key="up_ativos")
up_leitura = st.sidebar.file_uploader("Planilha de Leitura de Cocho (aba Leitura)", type=["xlsx"], key="up_leitura")

with st.sidebar.expander("🔗 Ou importar Leitura direto do Google Sheets"):
    st.caption(
        "A planilha precisa estar compartilhada como "
        "'Qualquer pessoa com o link pode visualizar'."
    )
    link_google_leitura = st.text_input(
        "Link da planilha (Google Sheets)", key="link_google_leitura",
        placeholder="Cole aqui o link de compartilhamento",
    )
    if st.button("🔄 Importar do Google Sheets", key="btn_google_leitura", width="stretch"):
        if not link_google_leitura:
            st.warning("Cole o link da planilha antes de importar.")
        else:
            try:
                arquivo = importer.baixar_google_sheet(link_google_leitura)
                df_l = importer.read_leitura(arquivo)
                n = db.upsert_leitura(df_l, "Google Sheets")
                st.success(f"Leitura: {n} linhas importadas do Google Sheets.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Erro ao importar do Google Sheets: {e}")

col_a, col_b = st.sidebar.columns(2)
if col_a.button("✅ Processar", width="stretch"):
    msgs = []
    try:
        if up_ativos is not None:
            df_a = importer.read_ativos(up_ativos)
            n = db.upsert_ativos(df_a, up_ativos.name)
            msgs.append(f"Consumo: {n} linhas importadas.")
        if up_leitura is not None:
            df_l = importer.read_leitura(up_leitura)
            n = db.upsert_leitura(df_l, up_leitura.name)
            msgs.append(f"Leitura: {n} linhas importadas.")
        if not msgs:
            st.sidebar.warning("Selecione ao menos um arquivo antes de processar.")
        else:
            for m in msgs:
                st.sidebar.success(m)
            st.cache_data.clear()
    except Exception as e:
        st.sidebar.error(f"Erro ao importar: {e}")

if col_b.button("🗑️ Limpar tudo", width="stretch"):
    st.session_state["confirm_wipe"] = True

if st.session_state.get("confirm_wipe"):
    st.sidebar.warning("Isso apaga TODO o histórico salvo. Confirma?")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Sim, apagar", width="stretch"):
        db.wipe_all()
        st.session_state["confirm_wipe"] = False
        st.cache_data.clear()
        st.sidebar.success("Base limpa.")
    if c2.button("Cancelar", width="stretch"):
        st.session_state["confirm_wipe"] = False

with st.sidebar.expander("📜 Últimas importações"):
    log = db.get_import_log()
    if log.empty:
        st.caption("Nenhuma importação ainda.")
    else:
        st.dataframe(log[["tipo", "arquivo", "linhas", "importado_em"]], hide_index=True, width="stretch")

st.sidebar.markdown("---")

# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------

ativos = db.load_all_ativos()
leitura = db.load_all_leitura()

if ativos.empty:
    st.markdown(f"""
    <div class="header-banner"><div><h1>Manejo de Cocho</h1>
    <span>Importe as planilhas de Consumo e Leitura na barra lateral para começar.</span></div></div>
    """, unsafe_allow_html=True)
    st.info("👈 Use a barra lateral para importar a planilha de **Consumo (Ativos)** e a de **Leitura de Cocho**.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — seleção de Curral / Lote
# ---------------------------------------------------------------------------

st.sidebar.markdown("### 🏠 Curral")
currais = sorted(ativos["CURRAL"].dropna().unique().tolist(), key=_natural_key)
data_max_geral = ativos["DATA"].max()
_data_max_leitura_geral = leitura["DATA"].max() if not leitura.empty else data_max_geral
_data_hoje_geral = max(data_max_geral, _data_max_leitura_geral)

# Currais que têm Consumo OU Leitura na data mais recente — usados para pular
# automaticamente currais "parados" (sem lançamento do dia) ao avançar pela
# tecla Enter na Decisão.
currais_com_dado_hoje = set(
    ativos.loc[ativos["DATA"] == _data_hoje_geral, "CURRAL"].dropna().unique().tolist()
) | set(
    leitura.loc[leitura["DATA"] == _data_hoje_geral, "CURRAL"].dropna().unique().tolist()
)


def _proximo_curral_com_dado(curral_atual):
    """Acha o próximo curral (em ordem, dando a volta) que tenha Consumo ou
    Leitura na data mais recente. Se nenhum tiver, cai no próximo da lista."""
    if curral_atual not in currais:
        return currais[0]
    idx = currais.index(curral_atual)
    n = len(currais)
    for passo in range(1, n + 1):
        candidato = currais[(idx + passo) % n]
        if candidato in currais_com_dado_hoje:
            return candidato
    return currais[(idx + 1) % n]


if "sel_curral" not in st.session_state or st.session_state["sel_curral"] not in currais:
    currais_hoje = sorted(ativos.loc[ativos["DATA"] == data_max_geral, "CURRAL"].dropna().unique().tolist(), key=_natural_key)
    st.session_state["sel_curral"] = currais_hoje[0] if currais_hoje else currais[0]

with st.sidebar.container(height=260):
    for curral_name in currais:
        is_sel = curral_name == st.session_state["sel_curral"]
        if st.button(curral_name, key=f"curral_{curral_name}", width="stretch",
                     type="primary" if is_sel else "secondary"):
            st.session_state["sel_curral"] = curral_name

sel_curral = st.session_state["sel_curral"]

# --- Limpeza de Cocho: individual (curral atual) e em lote (todos os currais) ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🧹 Limpeza de Cocho")
data_max_leitura = leitura["DATA"].max() if not leitura.empty else ativos["DATA"].max()
data_ref_default = max(ativos["DATA"].max(), data_max_leitura)
data_ref_limpeza = st.sidebar.date_input("Data de referência", value=data_ref_default.date())
data_ref_iso = data_ref_limpeza.strftime("%Y-%m-%d")

notas_curral_atual = db.load_notas(sel_curral)
limpou_atual = False
if not notas_curral_atual.empty:
    m = notas_curral_atual[notas_curral_atual["DATA"] == data_ref_iso]
    if not m.empty and pd.notna(m.iloc[0].get("LIMPEZA_COCHO")):
        limpou_atual = str(m.iloc[0]["LIMPEZA_COCHO"]).strip().upper() == "S"

limpou_check = st.sidebar.checkbox(
    f"Limpou o cocho — Curral {sel_curral}", value=limpou_atual,
    key=f"limpeza_{sel_curral}_{data_ref_iso}",
)
if limpou_check != limpou_atual:
    db.marcar_limpeza_cocho(data_ref_iso, sel_curral, "S" if limpou_check else "")

if st.sidebar.button("🧹 Marcar limpeza para TODOS os currais", width="stretch"):
    db.marcar_limpeza_cocho_todos(data_ref_iso, currais, "S")
    st.sidebar.success(f"Limpeza marcada para {len(currais)} currais em {data_ref_limpeza.strftime('%d/%m/%Y')}.")

st.sidebar.markdown("### 📦 Lote")
lotes_df = (
    ativos[ativos["CURRAL"] == sel_curral]
    .groupby("LOTE")["DATA"].max().reset_index().sort_values("DATA", ascending=False)
)
lotes = lotes_df["LOTE"].tolist()

if "sel_lote" not in st.session_state or st.session_state["sel_lote"] not in lotes:
    st.session_state["sel_lote"] = lotes[0] if lotes else None

with st.sidebar.container(height=200):
    for lote in lotes:
        ultima_data = lotes_df.loc[lotes_df["LOTE"] == lote, "DATA"].iloc[0]
        ativo_flag = "🟢" if ultima_data == data_max_geral else "⚪"
        is_sel = lote == st.session_state["sel_lote"]
        label = f"{ativo_flag} Lote {lote}"
        if st.button(label, key=f"lote_{lote}", width="stretch",
                     type="primary" if is_sel else "secondary"):
            st.session_state["sel_lote"] = lote

sel_lote = st.session_state["sel_lote"]

st.sidebar.markdown("---")
periodo = st.sidebar.selectbox("Período do histórico", ["Últimos 15 dias", "Últimos 30 dias", "Últimos 60 dias", "Tudo"], index=1)
n_dias_map = {"Últimos 15 dias": 15, "Últimos 30 dias": 30, "Últimos 60 dias": 60, "Tudo": None}
n_dias = n_dias_map[periodo]

st.sidebar.markdown("---")
st.sidebar.markdown("### 📤 Exportar Decisões")
todas_decisoes = db.load_all_decisoes()
if todas_decisoes.empty:
    st.sidebar.caption("Nenhuma decisão registrada ainda.")
else:
    export_df = todas_decisoes.rename(
        columns={
            "DATA": "Data", "CURRAL": "Curral", "LOTE": "Lote",
            "CONSUMO_DIA": "Consumo do Dia Anterior (KgMS)",
            "DECISAO": "Decisão (Kg)",
            "CONSUMO_PREVISTO": "Consumo Previsto (KgMS)",
        }
    )[["Data", "Curral", "Lote", "Consumo do Dia Anterior (KgMS)", "Decisão (Kg)", "Consumo Previsto (KgMS)"]]
    buffer = io.BytesIO()
    export_df.to_excel(buffer, index=False, sheet_name="Decisoes")
    st.sidebar.download_button(
        "⬇️ Baixar Decisões (.xlsx)",
        data=buffer.getvalue(),
        file_name="decisoes_manejo_cocho.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

# ---------------------------------------------------------------------------
# Monta a linha do tempo do curral/lote selecionado
# ---------------------------------------------------------------------------

sub_a = ativos[(ativos["CURRAL"] == sel_curral) & (ativos["LOTE"] == sel_lote)].sort_values("DATA").copy()
sub_l = leitura[leitura["CURRAL"] == sel_curral].sort_values("DATA").copy()
notas = db.load_notas(sel_curral)

# a Leitura é gravada por Curral (não por Lote). Para não misturar leituras de
# um lote anterior que já passou por este mesmo curral, só consideramos
# leituras a partir da data de entrada deste lote.
if not sub_a.empty:
    lote_start = sub_a["DATA"].min()
    sub_l = sub_l[sub_l["DATA"] >= lote_start]

# outer join: garante que um dia com Leitura mas ainda sem Consumo importado
# (ou vice-versa) apareça mesmo assim no histórico.
tl = pd.merge(sub_a, sub_l, on=["DATA", "CURRAL"], how="outer")
tl = pd.merge(tl, notas, on=["DATA", "CURRAL"], how="left")
tl = tl.sort_values("DATA")

# Blindagem: garante que todas as colunas que a tela espera existam, mesmo que
# a base de dados ainda esteja em uma versão mais antiga (evita KeyError).
for _col in [
    "H18", "H20", "H00", "H03", "H06", "SOBRA", "H12", "H16",
    "CONSUMO_MN", "FALTA_AGUA", "EQUIPAMENTOS", "TROCA_DIETA",
    "MOVIMENTACAO", "LIMPEZA_COCHO", "CHUVA", "T_MIN", "T_MAX",
]:
    if _col not in tl.columns:
        tl[_col] = None

# preenche para frente os dados "estáticos" do lote (peso, raça, dieta etc.)
# nos dias em que só chegou a Leitura de Cocho, sem o Consumo do dia.
# DIAS_CONF fica de fora dessa lista — ele é tratado à parte logo abaixo,
# incrementando +1 por dia (em vez de só repetir o último valor conhecido).
static_fill_cols = [
    "LOTE", "CAB", "RACA", "REBANHO_NOME", "CATEGORIA_NOME", "DATA_ENTRADA",
    "PESO_ENTRADA", "PESO_MEDIO_ATUAL", "RACAO_ATUAL",
    "TIPO_RACAO_ATUAL", "TIPO_DIAS_RACAO", "GMD_MEDIO",
]
tl[static_fill_cols] = tl[static_fill_cols].ffill()

_dias_conf_conhecidos = tl.loc[tl["DIAS_CONF"].notna(), ["DATA", "DIAS_CONF"]]


def _extrapola_dias_conf(row):
    if pd.notna(row["DIAS_CONF"]):
        return row["DIAS_CONF"]
    anteriores = _dias_conf_conhecidos[_dias_conf_conhecidos["DATA"] < row["DATA"]]
    if anteriores.empty:
        return np.nan
    ultimo = anteriores.iloc[-1]
    dias_passados = (row["DATA"] - ultimo["DATA"]).days
    return ultimo["DIAS_CONF"] + dias_passados


tl["DIAS_CONF"] = tl.apply(_extrapola_dias_conf, axis=1)

if n_dias:
    tl = tl.tail(n_dias)

if tl.empty:
    st.warning("Não há dados de consumo para este Curral/Lote no período.")
    st.stop()


# Protocolo de dietas por peso de entrada e sexo (dias de confinamento em que
# cada fase começa). "term" é o dia em que a Terminação começa, direto da
# tabela do protocolo (as vezes não bate exatamente com adapt+step1+step2
# por causa de arredondamento na própria tabela — usamos o valor dela).
_PROTOCOLO_DIETA = [
    {"sexo": "MACHO", "peso_min": 361, "peso_max": 99999, "adapt": 11, "step1": 5, "step2": 5, "term": 22},
    {"sexo": "MACHO", "peso_min": 331, "peso_max": 360, "adapt": 18, "step1": 5, "step2": 5, "term": 29},
    {"sexo": "MACHO", "peso_min": 301, "peso_max": 330, "adapt": 25, "step1": 5, "step2": 5, "term": 36},
    {"sexo": "MACHO", "peso_min": 270, "peso_max": 300, "adapt": 42, "step1": 5, "step2": 5, "term": 52},
    {"sexo": "FEMEA", "peso_min": 311, "peso_max": 99999, "adapt": 18, "step1": 5, "step2": 5, "term": 28},
    {"sexo": "FEMEA", "peso_min": 280, "peso_max": 310, "adapt": 25, "step1": 5, "step2": 5, "term": 35},
    {"sexo": "FEMEA", "peso_min": 250, "peso_max": 280, "adapt": 37, "step1": 5, "step2": 5, "term": 47},
]

FASE_CORES = {
    "Adaptação": "#A8E6A1",
    "Step1": "#6FCF57",
    "Step2": "#2E8B3D",
    "Terminação": "#0F4D1A",
    "DT": "#8ED1F0",
}


def _acha_protocolo(peso, sexo):
    if pd.isna(peso) or not sexo:
        return None
    candidatos = [p for p in _PROTOCOLO_DIETA if p["sexo"] == sexo and p["peso_min"] <= peso <= p["peso_max"]]
    if candidatos:
        return candidatos[0]
    mesmo_sexo = [p for p in _PROTOCOLO_DIETA if p["sexo"] == sexo]
    if not mesmo_sexo:
        return None
    return min(mesmo_sexo, key=lambda p: min(abs(peso - p["peso_min"]), abs(peso - p["peso_max"])))


def diet_phase(row):
    texto_tipo = str(row.get("TIPO_RACAO_ATUAL") or "").upper()
    texto_nome = str(row.get("RACAO_ATUAL") or "").upper()
    if "DT" in texto_tipo.split() or "DT" in texto_nome.split():
        return "DT"
    texto = texto_tipo or texto_nome

    categoria = str(row.get("CATEGORIA_NOME") or "").upper()
    sexo = "MACHO" if "MACHO" in categoria else ("FEMEA" if ("FEMEA" in categoria or "FÊMEA" in categoria) else None)
    peso = row.get("PESO_ENTRADA")
    dias = row.get("DIAS_CONF")

    proto = _acha_protocolo(peso, sexo) if sexo else None
    if proto is not None and pd.notna(dias):
        if dias <= proto["adapt"]:
            return "Adaptação"
        elif dias <= proto["adapt"] + proto["step1"]:
            return "Step1"
        elif dias < proto["term"]:
            return "Step2"
        else:
            return "Terminação"

    # sem peso/sexo suficientes pra aplicar o protocolo: usa o texto da dieta
    if "ADAPTA" in texto:
        return "Adaptação"
    if "CRESC" in texto:
        return "Step1"
    return "Terminação"


tl["FASE"] = tl.apply(diet_phase, axis=1)

# % MS da Dieta = Consumo de Matéria Seca / Consumo em Matéria Natural (as-fed).
# Preenchido para frente pois no dia do Inventory às vezes não há Consumo do
# mesmo dia — usamos a última % MS de dieta conhecida.
tl["MS_DIETA_PCT"] = (tl["CONSUMO_MS"] / tl["CONSUMO_MN"].replace(0, np.nan)).ffill()

# --- Diferença Ocorrida e Desvio Trato (calculados a partir das Decisões salvas) ---
# Diferença Ocorrida(D) = CMS real de D - CMS real de D-1
# Desvio Trato(D)        = CMS real de D - Consumo Previsto de D
#                           (Consumo Previsto de D = CMS de D-1 + Decisão registrada em D-1)
_cms_por_data = tl.set_index("DATA")["CONSUMO_MS"]
_decisoes_lote_calc = db.load_decisoes(sel_curral, sel_lote)
if not _decisoes_lote_calc.empty:
    _decisoes_lote_calc["DATA"] = pd.to_datetime(_decisoes_lote_calc["DATA"])
    _decisao_por_data = _decisoes_lote_calc.set_index("DATA")["DECISAO"]
else:
    _decisao_por_data = pd.Series(dtype=float)


def _diferenca_ocorrida(row):
    d_ant = row["DATA"] - pd.Timedelta(days=1)
    cms_ant = _cms_por_data.get(d_ant)
    if pd.isna(row["CONSUMO_MS"]) or cms_ant is None or pd.isna(cms_ant):
        return np.nan
    return row["CONSUMO_MS"] - cms_ant


def _desvio_trato_calc(row):
    d_ant = row["DATA"] - pd.Timedelta(days=1)
    cms_ant = _cms_por_data.get(d_ant)
    dec_ant = _decisao_por_data.get(d_ant) if len(_decisao_por_data) else None
    if pd.isna(row["CONSUMO_MS"]) or cms_ant is None or pd.isna(cms_ant) or dec_ant is None or pd.isna(dec_ant):
        return np.nan
    previsto = cms_ant + dec_ant
    return row["CONSUMO_MS"] - previsto


tl["DIFERENCA_OCORRIDA"] = tl.apply(_diferenca_ocorrida, axis=1)
tl["DESVIO_TRATO_CALC"] = tl.apply(_desvio_trato_calc, axis=1)

# ---------------------------------------------------------------------------
# Funções auxiliares da tabela (usadas no mini-histórico e no histórico completo)
# ---------------------------------------------------------------------------

OCC_FIELDS = ["FALTA_AGUA", "EQUIPAMENTOS", "TROCA_DIETA", "MOVIMENTACAO"]
OCC_LABELS = {
    "FALTA_AGUA": "Falta de Água", "EQUIPAMENTOS": "Equipamentos",
    "TROCA_DIETA": "Troca de Dieta", "MOVIMENTACAO": "Movimentação",
}


def _occ_flagged(v):
    return isinstance(v, str) and v.strip() != "" and v.strip().lower() != "nan"


def occ_count_badge(r):
    n = sum(1 for f in OCC_FIELDS if _occ_flagged(r.get(f)))
    if n == 0:
        return '<span class="occ-count occ-zero">0</span>'
    return f'<span class="occ-count occ-some">{n}</span>'


def badge(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "" or str(v).lower() == "nan":
        return '<span class="badge b-dash">–</span>'
    s = str(v).strip()
    cls = {"S": "b-s", "N": "b-n", "Dry": "b-dry", "Crumbs": "b-crumbs", "Inventory": "b-inv"}.get(s, "b-n")
    return f'<span class="badge {cls}">{s}</span>'


def numfmt(v, casas=2, suf=""):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '<span class="b-dash">–</span>'
    return f"{v:.{casas}f}{suf}"


def txt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return '<span class="b-dash">–</span>'
    return str(v)


def make_rows_def(detalhado=False):
    rows = [
        ("Data", lambda r: r["DATA"].strftime("%d/%b")),
        ("Animais (Cab)", lambda r: numfmt(r["CAB"], 0)),
        ("Dias Médios de Cocho", lambda r: numfmt(r["DIAS_CONF"], 0)),
        ("CMS (KgMS/cab/d)", lambda r: numfmt(r["CONSUMO_MS"], 2)),
        ("CMS PV (%PV/cab/d)", lambda r: numfmt(r["IMS_PV_DODIA"], 2, "%")),
        ("Escore 18:00", lambda r: badge(r.get("H18"))),
        ("Escore 20:00", lambda r: badge(r.get("H20"))),
        ("Escore 00:00", lambda r: badge(r.get("H00"))),
        ("Escore 03:00", lambda r: badge(r.get("H03"))),
        ("Escore 06:00", lambda r: badge(r.get("H06"))),
        ("Sobra (Kg)", lambda r: numfmt(r.get("SOBRA"), 0)),
        ("Escore 12:00", lambda r: badge(r.get("H12"))),
        ("Escore 16:00", lambda r: badge(r.get("H16"))),
        ("Ajuste Planejado (KgMS)", lambda r: numfmt(r.get("AJUSTE_KG_1"), 2)),
        ("Diferença Ocorrida (KgMS)", lambda r: numfmt(r.get("DIFERENCA_OCORRIDA"), 2)),
        ("Desvio Trato (KgMS)", lambda r: numfmt(r.get("DESVIO_TRATO_CALC"), 2)),
    ]
    if detalhado:
        rows += [(OCC_LABELS[f], (lambda f: (lambda r: txt(r.get(f))))(f)) for f in OCC_FIELDS]
    else:
        rows += [("Ocorrências", occ_count_badge)]
    rows += [
        ("Limpeza de Cocho", lambda r: txt(r.get("LIMPEZA_COCHO"))),
        ("Chuva (mm)", lambda r: numfmt(r.get("CHUVA"), 1)),
        ("T. Mínima (°C)", lambda r: numfmt(r.get("T_MIN"), 1)),
        ("T. Máxima (°C)", lambda r: numfmt(r.get("T_MAX"), 1)),
    ]
    return rows


def render_table_html(records, rows_def, wrap_class="tbl-wrap"):
    html = [f'<div class="{wrap_class}"><table class="cocho"><thead><tr><th class="rowlabel">Data</th>']
    for r in records:
        html.append(f'<th>{r["DATA"].strftime("%d/%b")}</th>')
    html.append("</tr></thead><tbody>")
    for label, fn in rows_def[1:]:
        html.append(f'<tr><td class="rowlabel">{label}</td>')
        for r in records:
            html.append(f"<td>{fn(r)}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


# ---------------------------------------------------------------------------
# Indicadores (CV de Consumo / % Leitura Desejada) — usados no cabeçalho
# ---------------------------------------------------------------------------

cms_recent = tl["CONSUMO_MS"].tail(5).dropna()
cv = (cms_recent.std() / cms_recent.mean() * 100) if len(cms_recent) > 1 and cms_recent.mean() else 0


def is_desejavel(campo, valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    v = str(valor).strip()
    if campo == "H06":
        return v in ("Crumbs", "Dry")
    return v.upper() == "S"


checks = []
for _, r in tl.iterrows():
    for campo in ["H20", "H00", "H03", "H06"]:
        res = is_desejavel(campo, r.get(campo))
        if res is not None:
            checks.append(res)
pct_desejada = (sum(checks) / len(checks) * 100) if checks else 0


def gauge_card(value, title, max_val, thresholds):
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={"text": title, "font": {"size": 22, "color": TEAL_DARK}},
        number={"suffix": "%", "font": {"size": 38, "color": TEAL_DARK}},
        gauge={
            "axis": {"range": [0, max_val], "tickfont": {"size": 13, "color": "#607070"}},
            "bar": {"color": TEAL_DARK, "thickness": 0.25},
            "bgcolor": "#eef2f2",
            "steps": thresholds,
        },
        domain={"x": [0, 1], "y": [0, 0.85]},
    ))
    fig_g.update_layout(
        height=260, margin=dict(l=15, r=15, t=55, b=5),
        paper_bgcolor="white", plot_bgcolor="white",
    )
    return fig_g


# ---------------------------------------------------------------------------
# Cabeçalho (com os gauges embutidos na faixa verde)
# ---------------------------------------------------------------------------

last = tl.iloc[-1]
data_ref_decisao = tl["DATA"].max()

dieta_txt = str(last["RACAO_ATUAL"]) if pd.notna(last["RACAO_ATUAL"]) else "-"
ms_dieta_series = tl["MS_DIETA_PCT"].dropna()
ms_dieta_last = ms_dieta_series.iloc[-1] if not ms_dieta_series.empty else None

with st.container(key="header_container"):
    htop1, htop2 = st.columns([2.6, 0.55])
    with htop1:
        st.markdown(
            f'<div style="display:flex; justify-content:space-between; align-items:flex-end;">'
            f'<div class="header-title-wrap"><h1>🐂 Manejo de Cocho</h1>'
            f'<span>Curral {sel_curral} · Lote {sel_lote}</span></div>'
            f'<div style="color:white; font-size:15px; font-weight:700;">'
            f'Atualizado em {datetime.now().strftime("%d/%m/%Y %H:%M")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with htop2:
        with st.container(key="setas_container"):
            st.markdown(
                '<div style="color:white; font-size:15px; text-align:center; '
                'font-weight:800; margin-bottom:6px;">↔️ Avançar / recuar curral</div>',
                unsafe_allow_html=True,
            )
            seta_esq, seta_dir = st.columns(2)
            idx_atual_curral = currais.index(sel_curral) if sel_curral in currais else 0
            with seta_esq:
                if st.button("◀ Anterior", key="btn_curral_anterior", width="stretch"):
                    st.session_state["sel_curral"] = currais[(idx_atual_curral - 1) % len(currais)]
                    st.session_state.pop("sel_lote", None)
                    st.rerun()
            with seta_dir:
                if st.button("Próximo ▶", key="btn_curral_proximo", width="stretch"):
                    st.session_state["sel_curral"] = currais[(idx_atual_curral + 1) % len(currais)]
                    st.session_state.pop("sel_lote", None)
                    st.rerun()

# ---------------------------------------------------------------------------
# Layout principal: gráfico + histórico completo (esquerda) |
#                   Decisão / Inventory / indicadores (direita)
# ---------------------------------------------------------------------------

col_left, col_right = st.columns([2.6, 0.55])

with col_left:
    mc = st.columns(5)

    def metric(col, label, value, small=False):
        cls = "value small" if small else "value"
        col.markdown(f'<div class="metric-card"><div class="label">{label}</div><div class="{cls}">{value}</div></div>', unsafe_allow_html=True)

    metric(mc[0], "Animais", int(last["CAB"]) if pd.notna(last["CAB"]) else "-")
    metric(mc[1], "Peso Entrada", f'{last["PESO_ENTRADA"]:.0f} kg' if pd.notna(last["PESO_ENTRADA"]) else "-")
    metric(mc[2], "Peso Atual", f'{last["PESO_MEDIO_ATUAL"]:.0f} kg' if pd.notna(last["PESO_MEDIO_ATUAL"]) else "-")
    metric(mc[3], "Raça", last["RACA"] if pd.notna(last["RACA"]) else "-")
    metric(mc[4], "Dias de Cocho", int(last["DIAS_CONF"]) if pd.notna(last["DIAS_CONF"]) else "-")

    # legenda das fases de dieta (cores usadas nas barras do gráfico)
    _legenda_html = "".join(
        f'<span style="display:inline-flex; align-items:center; margin-right:22px; '
        f'font-size:17px; font-weight:800; color:#222;">'
        f'<span style="display:inline-block; width:19px; height:19px; background:{cor}; '
        f'border-radius:3px; margin-right:7px; border:1px solid #999;"></span>{fase}</span>'
        for fase, cor in FASE_CORES.items()
    )
    st.markdown(f'<div style="margin:10px 0 4px 0;">{_legenda_html}</div>', unsafe_allow_html=True)

    _MES_ABREV = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
                  7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
    eixo_x = [f'{d.strftime("%d")}-{_MES_ABREV[d.month]}' for d in tl["DATA"]]
    cores_barras = tl["FASE"].map(FASE_CORES).fillna("#27AE60")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=eixo_x, y=tl["CONSUMO_MS"], name="CMS (KgMS/cab/d)",
        marker=dict(color=cores_barras, line=dict(color="white", width=1)), yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=eixo_x, y=tl["IMS_PV_DODIA"], name="CMS PV (%PV/cab/d)",
        mode="lines+markers+text",
        line=dict(color="#FF7A00", width=4),
        marker=dict(size=9, color="#FF7A00", line=dict(color="white", width=2)),
        text=[f"{v:.2f}" if pd.notna(v) else "" for v in tl["IMS_PV_DODIA"]],
        textposition="top center", textfont=dict(size=16, color="#CC5200", family="Arial Black"),
        yaxis="y2",
    ))
    fig.update_layout(
        height=480, margin=dict(l=10, r=10, t=60, b=10),
        plot_bgcolor="#FBFDFD", paper_bgcolor="white",
        bargap=0.15,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0,
                     font=dict(size=18, family="Arial Black", color="#222")),
        yaxis=dict(title="CMS (KgMS/cab/d)", side="left", gridcolor="#E8EFEF",
                    tickfont=dict(size=16, family="Arial Black", color="#222"),
                    title_font=dict(size=17, family="Arial Black", color="#222")),
        yaxis2=dict(title="CMS PV (%PV)", overlaying="y", side="right", showgrid=False,
                     tickfont=dict(size=16, family="Arial Black", color="#222"),
                     title_font=dict(size=17, family="Arial Black", color="#222")),
        xaxis=dict(title=None, gridcolor="#E8EFEF", type="category", tickangle=-45,
                    tickfont=dict(size=15, family="Arial Black", color="#222")),
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")

    # --- Histórico diário completo (logo abaixo do gráfico, mesma coluna) ---
    st.markdown("### 📋 Histórico diário")
    _export_placeholder = st.empty()
    mostrar_ocorrencias_detalhe = st.checkbox(
        "Mostrar ocorrências detalhadas (água, equipamentos, troca de dieta, movimentação)",
        value=False,
    )
    rows_def = make_rows_def(mostrar_ocorrencias_detalhe)
    records = tl.to_dict("records")
    st.markdown(render_table_html(records, rows_def), unsafe_allow_html=True)

    export_hist = pd.DataFrame({
        "Data": tl["DATA"].dt.strftime("%d/%m/%Y"),
        "Animais (Cab)": tl["CAB"],
        "Dias Médios de Cocho": tl["DIAS_CONF"],
        "CMS (KgMS/cab/d)": tl["CONSUMO_MS"],
        "CMS PV (%PV/cab/d)": tl["IMS_PV_DODIA"],
        "Escore 18:00": tl["H18"],
        "Escore 20:00": tl["H20"],
        "Escore 00:00": tl["H00"],
        "Escore 03:00": tl["H03"],
        "Escore 06:00": tl["H06"],
        "Sobra (Kg)": tl["SOBRA"],
        "Escore 12:00": tl["H12"],
        "Escore 16:00": tl["H16"],
        "Ajuste Planejado (KgMS)": tl["AJUSTE_KG_1"],
        "Diferença Ocorrida (KgMS)": tl["DIFERENCA_OCORRIDA"],
        "Desvio Trato (KgMS)": tl["DESVIO_TRATO_CALC"],
        "Falta de Água": tl["FALTA_AGUA"],
        "Equipamentos": tl["EQUIPAMENTOS"],
        "Troca de Dieta": tl["TROCA_DIETA"],
        "Movimentação": tl["MOVIMENTACAO"],
        "Limpeza de Cocho": tl["LIMPEZA_COCHO"],
        "Chuva (mm)": tl["CHUVA"],
        "T. Mínima (°C)": tl["T_MIN"],
        "T. Máxima (°C)": tl["T_MAX"],
    })
    buffer_hist = io.BytesIO()
    export_hist.to_excel(buffer_hist, index=False, sheet_name="Historico")
    _export_placeholder.download_button(
        "⬇️ Excel",
        data=buffer_hist.getvalue(),
        file_name=f"historico_{sel_curral}_lote{sel_lote}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.caption(
        "Linhas **Escore 18:00**, **Escore 12:00** e **Escore 16:00** foram adicionadas conforme solicitado "
        "(ficam em branco até a planilha de Leitura trazer essas colunas). "
        "'% Leitura Desejada' considera desejável: 20h=S, 00h=S, 03h=S e 06h=Crumbs ou Dry. "
        "**Diferença Ocorrida** = CMS de hoje − CMS de ontem. **Desvio Trato** = CMS de hoje − Consumo "
        "Previsto de hoje (CMS de ontem + Decisão registrada ontem) — por isso só aparece nos dias em "
        "que havia uma Decisão salva no dia anterior. "
        "Marque a caixa acima para ver o detalhe de cada ocorrência; desmarcada, elas somam em uma "
        "única linha 'Ocorrências' com a contagem do dia."
    )

with col_right:
    decisoes_lote = db.load_decisoes(sel_curral, sel_lote)
    decisao_hoje_atual = 0.0
    ja_tem_decisao_hoje = False
    if not decisoes_lote.empty:
        match = decisoes_lote[decisoes_lote["DATA"] == data_ref_decisao.strftime("%Y-%m-%d")]
        if not match.empty and pd.notna(match.iloc[0]["DECISAO"]):
            decisao_hoje_atual = float(match.iloc[0]["DECISAO"])
            ja_tem_decisao_hoje = True

    # O consumo de "hoje" só é conhecido depois que o trato acontece — então a
    # Decisão de hoje soma sempre o CMS do dia ANTERIOR (D-1), não do dia atual.
    dia_anterior = tl[(tl["DATA"] < data_ref_decisao) & tl["CONSUMO_MS"].notna()]
    if not dia_anterior.empty:
        linha_cms_ref = dia_anterior.iloc[-1]
        cms_hoje_val = float(linha_cms_ref["CONSUMO_MS"])
        data_cms_ref = linha_cms_ref["DATA"]
    else:
        cms_hoje_val = None
        data_cms_ref = None

    key_decisao = f"decisao_input_{sel_curral}_{sel_lote}"
    data_ref_iso_decisao = data_ref_decisao.strftime("%Y-%m-%d")

    def _salvar_e_avancar():
        valor = st.session_state.get(key_decisao, decisao_hoje_atual)
        db.upsert_decisao(data_ref_iso_decisao, sel_curral, sel_lote, valor)
        st.toast(f"Decisão salva para {sel_curral} / Lote {sel_lote}: {valor:+.2f} Kg", icon="✅")
        st.session_state["sel_curral"] = _proximo_curral_com_dado(sel_curral)
        st.session_state.pop("sel_lote", None)

    with st.container(key="decisao_container"):
        st.markdown('<div class="decisao-big-title">✅ DECISÃO — ajuste do dia</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="decisao-preview">Data de referência: {data_ref_decisao.strftime("%d/%m/%Y")}</div>',
            unsafe_allow_html=True,
        )
        if ja_tem_decisao_hoje:
            st.markdown(
                f'<div class="decisao-preview" style="font-weight:800; font-size:16px;">'
                f'✏️ Já existe uma decisão registrada hoje: {decisao_hoje_atual:+.2f} Kg — '
                f'pode corrigir no campo abaixo e salvar de novo.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="decisao-preview" style="font-size:15px; opacity:0.85;">'
                'Nenhuma decisão registrada ainda hoje para este curral/lote.</div>',
                unsafe_allow_html=True,
            )
        nova_decisao = st.number_input(
            "Ajuste de hoje (Kg MS/cab, + aumenta / − reduz) — Enter salva e vai para o próximo curral",
            value=decisao_hoje_atual, step=0.05, format="%.2f",
            key=key_decisao, on_change=_salvar_e_avancar,
        )

    if cms_hoje_val is not None:
        previsto = cms_hoje_val + nova_decisao
        st.markdown(
            f'<div class="decisao-preview" style="color:{TEAL_DARK}; font-size:28px; font-weight:800;">'
            f'📌 Consumo Previsto: <b>{previsto:.2f} KgMS/cab/d</b></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:15px; color:#607070; font-weight:600;">'
            'Sem CMS do dia anterior para calcular o Consumo Previsto ainda.</div>',
            unsafe_allow_html=True,
        )

    if st.button("💾 Salvar decisão e ir para o próximo curral", width="stretch"):
        _salvar_e_avancar()
        st.rerun()

    # devolve o foco pro campo de decisão depois de cada rerun, pra dar pra
    # seguir digitando com Enter sem precisar tocar no mouse. Usa um "nonce"
    # (timestamp) pra garantir que o conteúdo mude a cada rerun e o navegador
    # execute o script de novo.
    _nonce = datetime.now().strftime("%H%M%S%f")
    st.iframe(
        f"""
        <script>
        /* nonce: {_nonce} */
        (function() {{
            let tentativas = 0;
            const timer = setInterval(function() {{
                tentativas++;
                try {{
                    const doc = window.parent.document;
                    const el = doc.querySelector('.st-key-decisao_container input[type="number"]');
                    if (el) {{
                        el.focus();
                        el.select();
                        clearInterval(timer);
                    }}
                }} catch (e) {{}}
                if (tentativas > 30) {{ clearInterval(timer); }}
            }}, 100);
        }})();
        </script>
        """,
        height=1,
    )

    with st.expander("Histórico de decisões deste lote"):
        if decisoes_lote.empty:
            st.caption("Nenhuma decisão registrada ainda.")
        else:
            st.dataframe(decisoes_lote, hide_index=True, width="stretch")

    st.markdown(
        '<div class="decisao-title" style="font-size:16px; margin-bottom:10px;">'
        '🧮 Sem / Com Limpeza de Cocho</div>',
        unsafe_allow_html=True,
    )

    linha_hoje = tl[tl["DATA"] == data_ref_decisao]
    r_hoje = linha_hoje.iloc[0] if not linha_hoje.empty else None
    hoje_e_inventory = r_hoje is not None and str(r_hoje.get("H06")).strip().upper() == "INVENTORY"

    if not hoje_e_inventory:
        st.markdown(
            f'''
            <div class="decisao-box" style="border-left-color:#ccc;">
                <div style="font-size:19px; color:#3a4a4a; margin-bottom:8px; font-weight:800;">
                    Hoje ({data_ref_decisao.strftime("%d/%m/%Y")}) não teve leitura Inventory — sem retirada de comida a calcular.
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span style="font-size:22px;font-weight:800;">SEM limpeza de cocho</span><b style="color:#999; font-size:24px;">0,00 Kg</b>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-size:22px;font-weight:800;">COM limpeza de cocho</span><b style="color:#999; font-size:24px;">0,00 Kg</b>
                </div>
            </div>
            ''', unsafe_allow_html=True,
        )
    else:
        r_inv = r_hoje
        sobra_inv = r_inv.get("SOBRA")
        # a Sobra encontrada na leitura de hoje se refere ao trato de ONTEM —
        # então cab e %MS da dieta usados na conta também são do dia anterior.
        dia_ref_inv = tl[tl["DATA"] < r_inv["DATA"]]
        r_ref = dia_ref_inv.iloc[-1] if not dia_ref_inv.empty else r_inv
        cab_inv = r_ref.get("CAB")

        # Busca o % MS da Dieta em TODO o histórico do lote (não só no período
        # visível na tela), pra não falhar se o dado válido estiver fora da
        # janela de "últimos 30 dias" ou se faltar CONSUMO_MN nesses dias.
        hist_lote = ativos[(ativos["CURRAL"] == sel_curral) & (ativos["LOTE"] == sel_lote)].copy()
        hist_lote["_MS_RATIO"] = hist_lote["CONSUMO_MS"] / hist_lote["CONSUMO_MN"].replace(0, np.nan)
        validos = hist_lote.dropna(subset=["_MS_RATIO"])
        if not validos.empty:
            anteriores = validos[validos["DATA"] <= r_ref["DATA"]]
            linha_ratio = anteriores.iloc[-1] if not anteriores.empty else validos.iloc[-1]
            ms_ratio_inv = linha_ratio["_MS_RATIO"]
        else:
            ms_ratio_inv = None

        if pd.isna(sobra_inv):
            st.caption("Leitura Inventory de hoje sem valor de Sobra (Kg) preenchido.")
        elif pd.isna(cab_inv) or not cab_inv:
            st.caption("Sem número de animais no dia de referência para calcular.")
        elif ms_ratio_inv is None or pd.isna(ms_ratio_inv):
            st.caption(
                "⚠️ Falta o % MS da Dieta para calcular (vem do Consumo — "
                "reimporte a planilha de Consumo mais recente para preencher esse campo)."
            )
        else:
            x = sobra_inv / cab_inv
            y = x * ms_ratio_inv
            com_limpeza = -y
            sem_limpeza = -2 * y
            st.markdown(
                f'''
                <div class="decisao-box" style="border-left-color:{RED};">
                    <div style="font-size:19px; color:#3a4a4a; margin-bottom:8px; font-weight:800;">
                        Inventory de hoje ({r_inv["DATA"].strftime("%d/%m/%Y")}), trato de {r_ref["DATA"].strftime("%d/%m")}
                        — Sobra {sobra_inv:.0f} Kg ÷ {cab_inv:.0f} cab × {ms_ratio_inv*100:.1f}% MS
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="font-size:22px;font-weight:800;">SEM limpeza de cocho</span><b style="color:{RED}; font-size:25px;">{sem_limpeza:.2f} Kg</b>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-size:22px;font-weight:800;">COM limpeza de cocho</span><b style="color:{ORANGE}; font-size:25px;">{com_limpeza:.2f} Kg</b>
                    </div>
                </div>
                ''', unsafe_allow_html=True,
            )

    metric(st, "% MS Dieta", f"{ms_dieta_last * 100:.1f}%" if ms_dieta_last is not None else "-")
    metric(st, "Dieta Atual", dieta_txt, small=True)

    st.plotly_chart(gauge_card(cv, "CV Consumo (5d)", 25,
                     [{"range": [0, 8], "color": "rgba(63,163,77,0.9)"},
                      {"range": [8, 12], "color": "rgba(242,201,76,0.9)"},
                      {"range": [12, 25], "color": "rgba(231,76,60,0.9)"}]),
                     width="stretch", config={"displayModeBar": False})
    st.plotly_chart(gauge_card(pct_desejada, "% Leitura Desej.", 100,
                     [{"range": [0, 50], "color": "rgba(231,76,60,0.9)"},
                      {"range": [50, 80], "color": "rgba(242,201,76,0.9)"},
                      {"range": [80, 100], "color": "rgba(63,163,77,0.9)"}]),
                     width="stretch", config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Edição de ocorrências manuais
# ---------------------------------------------------------------------------

with st.expander("✏️ Registrar ocorrências manuais (água, equipamento, clima, etc.)"):
    edit_df = tl[["DATA", "FALTA_AGUA", "EQUIPAMENTOS", "TROCA_DIETA", "MOVIMENTACAO",
                  "LIMPEZA_COCHO", "CHUVA", "T_MIN", "T_MAX"]].copy()
    edit_df["DATA"] = edit_df["DATA"].dt.strftime("%Y-%m-%d")
    edited = st.data_editor(edit_df, hide_index=True, width="stretch", key="notas_editor")
    if st.button("💾 Salvar ocorrências"):
        save_df = edited.copy()
        save_df["CURRAL"] = sel_curral
        save_df["LIMPOU"] = None
        n = db.upsert_notas(save_df)
        st.success(f"{n} dias salvos para o curral {sel_curral}.")
        st.cache_data.clear()
