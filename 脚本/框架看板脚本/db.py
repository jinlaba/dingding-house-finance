# -*- coding: utf-8 -*-
"""
db.py — 数据库连接共享模块
所有 m*.py 脚本通过 from db import get_engine 取数
"""
import os
from sqlalchemy import create_engine, text

DB_NAME = "顶鼎"
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        if not DB_PASSWORD:
            print("⚠️ DB_PASSWORD 为空，若数据库要求密码将连接失败")
        _engine = create_engine(
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
            pool_pre_ping=True
        )
    return _engine

def query_df(sql, params=None):
    """执行 SQL 返回 DataFrame"""
    import pandas as pd
    if params is None:
        return pd.read_sql_query(sql, get_engine())
    return pd.read_sql_query(sql, get_engine(), params=params)

def query_list(sql, params=None):
    """执行 SQL 返回 list of dict"""
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]

# 中间数据输出目录
import pathlib
SCRIPT_DIR = pathlib.Path(__file__).parent
MID_DIR = SCRIPT_DIR / "中间数据"
MID_DIR.mkdir(exist_ok=True)

def save_json(data, name):
    """保存 JSON 到中间数据目录（清洗 NaN/Infinity → None，保证严格 JSON）"""
    import json, math

    def clean(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        if isinstance(v, dict):
            return {k: clean(val) for k, val in v.items()}
        if isinstance(v, list):
            return [clean(val) for val in v]
        return v

    path = MID_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean(data), f, ensure_ascii=False, default=str, indent=2)
    print(f"  -> {path.name}")

def save_xlsx(df, name, sheet_name="数据"):
    """保存 DataFrame 到中间数据目录"""
    path = MID_DIR / f"{name}.xlsx"
    df.to_excel(path, index=False, sheet_name=sheet_name, engine="openpyxl")
    print(f"  -> {path.name}")

def month_over_month(df, month_col, value_col, org_col=None):
    """计算环比：本月 vs 上月"""
    import pandas as pd
    if org_col:
        df = df.sort_values([org_col, month_col])
        df[f"{value_col}_环比"] = df.groupby(org_col)[value_col].pct_change()
    else:
        df = df.sort_values(month_col)
        df[f"{value_col}_环比"] = df[value_col].pct_change()
    return df

def format_pct(v):
    """格式化百分比"""
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    return f"{v*100:.1f}%"

def format_money(v):
    """格式化金额（万元）"""
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    return f"{v/10000:.1f}万"
