"""
db.py — camada de persistência do Manejo de Cocho.

Usa PostgreSQL (ex.: um projeto gratuito no Supabase) para que o histórico
de consumo e leituras de cocho fique acessível de qualquer lugar, com
várias pessoas usando o app ao mesmo tempo — inclusive quando o app está
hospedado no Streamlit Community Cloud.

Onde configurar a conexão:
  - Rodando localmente: crie o arquivo `.streamlit/secrets.toml` (na mesma
    pasta do app.py) com:
        SUPABASE_DB_URL = "postgresql://postgres:SENHA@HOST:5432/postgres"
  - Rodando no Streamlit Community Cloud: cole a mesma linha em
    "Settings" → "Secrets" do seu app, pelo site share.streamlit.io.
"""

import os
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_engine():
    db_url = None
    try:
        db_url = st.secrets.get("SUPABASE_DB_URL")
    except Exception:
        db_url = None
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "Não achei a conexão com o banco. Defina SUPABASE_DB_URL em "
            ".streamlit/secrets.toml (local) ou em Settings → Secrets "
            "(Streamlit Community Cloud)."
        )
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)


# ---------------------------------------------------------------------------
# Esquema (identificadores entre aspas para preservar MAIÚSCULAS, já que o
# Postgres, sem aspas, transformaria tudo em minúsculo por padrão)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS ativos (
    "DATA" DATE NOT NULL,
    "CURRAL" TEXT NOT NULL,
    "LOTE" BIGINT NOT NULL,
    "CAB" INTEGER,
    "RACA" TEXT,
    "REBANHO_NOME" TEXT,
    "CATEGORIA_NOME" TEXT,
    "DATA_ENTRADA" DATE,
    "DIAS_CONF" INTEGER,
    "PESO_ENTRADA" DOUBLE PRECISION,
    "PESO_MEDIO_ATUAL" DOUBLE PRECISION,
    "RACAO_ATUAL" TEXT,
    "TIPO_RACAO_ATUAL" TEXT,
    "TIPO_DIAS_RACAO" INTEGER,
    "GMD_MEDIO" DOUBLE PRECISION,
    "CONSUMO_MS" DOUBLE PRECISION,
    "CONSUMO_MN" DOUBLE PRECISION,
    "IMS_PV_DODIA" DOUBLE PRECISION,
    "AJUSTE_KG_1" DOUBLE PRECISION,
    "AJUSTE_KG_2" DOUBLE PRECISION,
    "AJUSTE_KG_3" DOUBLE PRECISION,
    "LEITURA1" DOUBLE PRECISION,
    "LEITURA2" DOUBLE PRECISION,
    "LEITURA3" DOUBLE PRECISION,
    PRIMARY KEY ("DATA", "CURRAL", "LOTE")
);

CREATE TABLE IF NOT EXISTS leitura (
    "DATA" DATE NOT NULL,
    "CURRAL" TEXT NOT NULL,
    "H18" TEXT,
    "H20" TEXT,
    "H00" TEXT,
    "H03" TEXT,
    "H06" TEXT,
    "SOBRA" DOUBLE PRECISION,
    "H12" TEXT,
    "H16" TEXT,
    PRIMARY KEY ("DATA", "CURRAL")
);

CREATE TABLE IF NOT EXISTS notas (
    "DATA" DATE NOT NULL,
    "CURRAL" TEXT NOT NULL,
    "LIMPOU" TEXT,
    "FALTA_AGUA" TEXT,
    "EQUIPAMENTOS" TEXT,
    "TROCA_DIETA" TEXT,
    "MOVIMENTACAO" TEXT,
    "LIMPEZA_COCHO" TEXT,
    "CHUVA" DOUBLE PRECISION,
    "T_MIN" DOUBLE PRECISION,
    "T_MAX" DOUBLE PRECISION,
    PRIMARY KEY ("DATA", "CURRAL")
);

CREATE TABLE IF NOT EXISTS decisoes (
    "DATA" DATE NOT NULL,
    "CURRAL" TEXT NOT NULL,
    "LOTE" BIGINT NOT NULL,
    "DECISAO" DOUBLE PRECISION,
    "registrado_em" TEXT,
    PRIMARY KEY ("DATA", "CURRAL", "LOTE")
);

CREATE TABLE IF NOT EXISTS settings (
    "key" TEXT PRIMARY KEY,
    "value" TEXT
);

CREATE TABLE IF NOT EXISTS import_log (
    id SERIAL PRIMARY KEY,
    tipo TEXT,
    arquivo TEXT,
    linhas INTEGER,
    importado_em TEXT
);
"""


def init_db():
    engine = get_engine()
    with engine.begin() as conn:
        for statement in SCHEMA.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
    _migrate()


def _migrate():
    """Adiciona colunas novas em bases já existentes, sem apagar nada."""
    novas_colunas = {"ativos": [("CONSUMO_MN", "DOUBLE PRECISION")], "leitura": [("H16", "TEXT")]}
    engine = get_engine()
    with engine.begin() as conn:
        for tabela, colunas in novas_colunas.items():
            existentes = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :tabela"
                ),
                {"tabela": tabela},
            ).fetchall()
            existentes = {row[0] for row in existentes}
            for coluna, tipo in colunas:
                if coluna not in existentes:
                    conn.execute(text(f'ALTER TABLE {tabela} ADD COLUMN "{coluna}" {tipo}'))


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------

ATIVOS_COLS = [
    "DATA", "CURRAL", "LOTE", "CAB", "RACA", "REBANHO_NOME", "CATEGORIA_NOME",
    "DATA_ENTRADA", "DIAS_CONF", "PESO_ENTRADA", "PESO_MEDIO_ATUAL",
    "RACAO_ATUAL", "TIPO_RACAO_ATUAL", "TIPO_DIAS_RACAO", "GMD_MEDIO",
    "CONSUMO_MS", "CONSUMO_MN", "IMS_PV_DODIA", "AJUSTE_KG_1", "AJUSTE_KG_2", "AJUSTE_KG_3",
    "LEITURA1", "LEITURA2", "LEITURA3",
]

LEITURA_COLS = ["DATA", "CURRAL", "H18", "H20", "H00", "H03", "H06", "SOBRA", "H12", "H16"]

NOTAS_COLS = [
    "DATA", "CURRAL", "LIMPOU", "FALTA_AGUA", "EQUIPAMENTOS", "TROCA_DIETA",
    "MOVIMENTACAO", "LIMPEZA_COCHO", "CHUVA", "T_MIN", "T_MAX",
]


def _to_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)) or pd.isna(val):
        return None
    return pd.to_datetime(val).date()


def _clean(v):
    if isinstance(v, float) and pd.isna(v):
        return None
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return None
    return v


def _log_import(conn, tipo, arquivo_nome, linhas):
    conn.execute(
        text(
            'INSERT INTO import_log (tipo, arquivo, linhas, importado_em) '
            'VALUES (:tipo, :arquivo, :linhas, :importado_em)'
        ),
        {
            "tipo": tipo, "arquivo": arquivo_nome, "linhas": linhas,
            "importado_em": datetime.now().isoformat(timespec="seconds"),
        },
    )


def upsert_ativos(df: pd.DataFrame, arquivo_nome: str = "") -> int:
    """Recebe o DataFrame já normalizado (ver importer.read_ativos) e grava/atualiza no Postgres."""
    engine = get_engine()
    cols_sql = ", ".join(f'"{c}"' for c in ATIVOS_COLS)
    placeholders = ", ".join(f":{c}" for c in ATIVOS_COLS)
    update_cols = [c for c in ATIVOS_COLS if c not in ("DATA", "CURRAL", "LOTE")]
    update_sql = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
    sql = text(
        f'INSERT INTO ativos ({cols_sql}) VALUES ({placeholders}) '
        f'ON CONFLICT ("DATA", "CURRAL", "LOTE") DO UPDATE SET {update_sql}'
    )
    registros = []
    for _, r in df.iterrows():
        row = {}
        for c in ATIVOS_COLS:
            v = r.get(c)
            if c in ("DATA", "DATA_ENTRADA"):
                v = _to_date(v)
            elif isinstance(v, float) and pd.isna(v):
                v = None
            row[c] = v
        registros.append(row)
    with engine.begin() as conn:
        if registros:
            conn.execute(sql, registros)
        _log_import(conn, "ATIVOS", arquivo_nome, len(registros))
    return len(registros)


def upsert_leitura(df: pd.DataFrame, arquivo_nome: str = "") -> int:
    engine = get_engine()
    cols_sql = ", ".join(f'"{c}"' for c in LEITURA_COLS)
    placeholders = ", ".join(f":{c}" for c in LEITURA_COLS)
    update_cols = [c for c in LEITURA_COLS if c not in ("DATA", "CURRAL")]
    update_sql = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
    sql = text(
        f'INSERT INTO leitura ({cols_sql}) VALUES ({placeholders}) '
        f'ON CONFLICT ("DATA", "CURRAL") DO UPDATE SET {update_sql}'
    )
    registros = []
    for _, r in df.iterrows():
        row = {"DATA": _to_date(r.get("DATA"))}
        for c in LEITURA_COLS[1:]:
            v = r.get(c)
            if isinstance(v, float) and pd.isna(v):
                v = None
            row[c] = v
        registros.append(row)
    with engine.begin() as conn:
        if registros:
            conn.execute(sql, registros)
        _log_import(conn, "LEITURA", arquivo_nome, len(registros))
    return len(registros)


def upsert_notas(df: pd.DataFrame) -> int:
    engine = get_engine()
    cols_sql = ", ".join(f'"{c}"' for c in NOTAS_COLS)
    placeholders = ", ".join(f":{c}" for c in NOTAS_COLS)
    update_cols = [c for c in NOTAS_COLS if c not in ("DATA", "CURRAL")]
    update_sql = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
    sql = text(
        f'INSERT INTO notas ({cols_sql}) VALUES ({placeholders}) '
        f'ON CONFLICT ("DATA", "CURRAL") DO UPDATE SET {update_sql}'
    )
    registros = []
    for _, r in df.iterrows():
        row = {"DATA": _to_date(r.get("DATA"))}
        for c in NOTAS_COLS[1:]:
            v = r.get(c)
            if isinstance(v, float) and pd.isna(v):
                v = None
            row[c] = v
        registros.append(row)
    with engine.begin() as conn:
        if registros:
            conn.execute(sql, registros)
    return len(registros)


# ---------------------------------------------------------------------------
# Leitura (SELECT)
# ---------------------------------------------------------------------------

def load_all_ativos() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql_query(text('SELECT * FROM ativos'), engine)
    if not df.empty:
        df["DATA"] = pd.to_datetime(df["DATA"])
        df["DATA_ENTRADA"] = pd.to_datetime(df["DATA_ENTRADA"])
    return df


def load_all_leitura() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql_query(text('SELECT * FROM leitura'), engine)
    if not df.empty:
        df["DATA"] = pd.to_datetime(df["DATA"])
    return df


def load_notas(curral: str) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql_query(
        text('SELECT * FROM notas WHERE "CURRAL" = :curral'), engine, params={"curral": curral},
    )
    if not df.empty:
        df["DATA"] = pd.to_datetime(df["DATA"])
    return df


def get_setting(key: str, default=None):
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text('SELECT "value" FROM settings WHERE "key" = :key'), {"key": key}
        ).fetchone()
    return row[0] if row else default


def set_setting(key: str, value):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                'INSERT INTO settings ("key", "value") VALUES (:key, :value) '
                'ON CONFLICT ("key") DO UPDATE SET "value" = EXCLUDED."value"'
            ),
            {"key": key, "value": str(value)},
        )


def upsert_decisao(data_iso: str, curral: str, lote: int, decisao):
    """decisao: ajuste em Kg MS/cab (número, ex.: 0.3 ou -0.2)."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                'INSERT INTO decisoes ("DATA", "CURRAL", "LOTE", "DECISAO", "registrado_em") '
                'VALUES (:data, :curral, :lote, :decisao, :registrado_em) '
                'ON CONFLICT ("DATA", "CURRAL", "LOTE") DO UPDATE SET '
                '"DECISAO" = EXCLUDED."DECISAO", "registrado_em" = EXCLUDED."registrado_em"'
            ),
            {
                "data": _to_date(data_iso), "curral": curral, "lote": int(lote),
                "decisao": float(decisao),
                "registrado_em": datetime.now().isoformat(timespec="seconds"),
            },
        )


def _add_consumo_previsto(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["CONSUMO_DIA"] = []
        df["CONSUMO_PREVISTO"] = []
        return df
    df["DECISAO"] = pd.to_numeric(df["DECISAO"], errors="coerce")
    df["CONSUMO_DIA"] = pd.to_numeric(df["CONSUMO_DIA"], errors="coerce")
    df["CONSUMO_PREVISTO"] = df["CONSUMO_DIA"] + df["DECISAO"]
    return df


def load_decisoes(curral: str = None, lote: int = None) -> pd.DataFrame:
    engine = get_engine()
    query = (
        'SELECT d."DATA", d."CURRAL", d."LOTE", a."CONSUMO_MS" as "CONSUMO_DIA", d."DECISAO" '
        'FROM decisoes d '
        'LEFT JOIN ativos a ON a."DATA" = d."DATA" - 1 AND a."CURRAL" = d."CURRAL" AND a."LOTE" = d."LOTE"'
    )
    params = {}
    conds = []
    if curral is not None:
        conds.append('d."CURRAL" = :curral')
        params["curral"] = curral
    if lote is not None:
        conds.append('d."LOTE" = :lote')
        params["lote"] = int(lote)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += ' ORDER BY d."DATA" DESC'
    df = pd.read_sql_query(text(query), engine, params=params)
    if not df.empty:
        df["DATA"] = pd.to_datetime(df["DATA"])
    return _add_consumo_previsto(df)


def load_all_decisoes() -> pd.DataFrame:
    engine = get_engine()
    query = (
        'SELECT d."DATA", d."CURRAL", d."LOTE", a."CONSUMO_MS" as "CONSUMO_DIA", d."DECISAO" '
        'FROM decisoes d '
        'LEFT JOIN ativos a ON a."DATA" = d."DATA" - 1 AND a."CURRAL" = d."CURRAL" AND a."LOTE" = d."LOTE" '
        'ORDER BY d."DATA" DESC, d."CURRAL", d."LOTE"'
    )
    df = pd.read_sql_query(text(query), engine)
    if not df.empty:
        df["DATA"] = pd.to_datetime(df["DATA"])
    return _add_consumo_previsto(df)


def marcar_limpeza_cocho(data_iso: str, curral: str, valor: str = "S"):
    """Marca (ou desmarca, valor='') a Limpeza de Cocho de um curral num dia."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                'INSERT INTO notas ("DATA", "CURRAL", "LIMPEZA_COCHO") '
                'VALUES (:data, :curral, :valor) '
                'ON CONFLICT ("DATA", "CURRAL") DO UPDATE SET "LIMPEZA_COCHO" = EXCLUDED."LIMPEZA_COCHO"'
            ),
            {"data": _to_date(data_iso), "curral": curral, "valor": valor},
        )


def marcar_limpeza_cocho_todos(data_iso: str, currais: list, valor: str = "S"):
    for c in currais:
        marcar_limpeza_cocho(data_iso, c, valor)


def get_import_log(limit=10) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql_query(
        text('SELECT * FROM import_log ORDER BY id DESC LIMIT :limit'), engine, params={"limit": limit},
    )
    return df


def wipe_all():
    engine = get_engine()
    with engine.begin() as conn:
        for tabela in ["ativos", "leitura", "notas", "import_log"]:
            conn.execute(text(f"DELETE FROM {tabela}"))
