# -*- coding: utf-8 -*-
"""
z00_建视图.py — 执行 00~08 SQL 文件，在数据库创建/替换视图
用法：python z00_建视图.py            # 全量建
      python z00_建视图.py --only 03  # 只建 03_收支.sql
"""
import sys, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sqlalchemy import text
from db import get_engine

SCRIPT_DIR = pathlib.Path(__file__).parent

# 执行顺序（M0 维度是基础）
SQL_FILES = [
    "00_维度.sql",
    "01_规模.sql",
    "02_出租率.sql",
    "03_收支.sql",
    "04_资金.sql",
    "05_财务.sql",
    "06_利润.sql",
    "07_组织.sql",
    "08_说明.sql",
]


def split_sql(sql):
    """健壮切分 SQL：处理 $$ 美元引用块、单引号字符串、注释行"""
    statements = []
    current = []
    in_dollar = False
    in_quote = False
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        # 行注释
        if not in_dollar and not in_quote and c == '-' and i + 1 < n and sql[i+1] == '-':
            # 跳过到行尾
            while i < n and sql[i] != '\n':
                i += 1
            continue
        # 美元引用块 $$...$$
        if not in_quote and sql.startswith('$$', i):
            in_dollar = not in_dollar
            current.append('$$')
            i += 2
            continue
        # 单引号
        if c == "'":
            if in_quote:
                # 转义引号 ''
                if i + 1 < n and sql[i+1] == "'":
                    current.append("''")
                    i += 2
                    continue
                in_quote = False
            else:
                in_quote = True
            current.append(c)
            i += 1
            continue
        # 分号切分
        if c == ';' and not in_dollar and not in_quote:
            statements.append(''.join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    if ''.join(current).strip():
        statements.append(''.join(current))
    return [s.strip() for s in statements if s.strip()]


def run_sql_file(engine, path):
    """执行单个 SQL 文件（支持多条语句）"""
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    statements = split_sql(sql)
    executed = 0
    with engine.begin() as conn:
        for s in statements:
            try:
                conn.execute(text(s))
                executed += 1
            except Exception as e:
                print(f"  ⚠️ 语句失败: {str(e)[:200]}")
                print(f"     语句前80字: {s[:80]}")
    return executed


def main():
    parser = argparse.ArgumentParser(description="建视图")
    parser.add_argument("--only", default=None, help="只建指定文件前缀，如 03")
    args = parser.parse_args()

    from db import get_engine
    engine = get_engine()
    print("=" * 60)
    print("🚀 建视图")
    print("=" * 60)

    files = SQL_FILES
    if args.only:
        files = [f for f in files if f.startswith(args.only)]
        if not files:
            print(f"❌ 未找到前缀 {args.only} 的 SQL 文件")
            sys.exit(1)

    for fname in files:
        path = SCRIPT_DIR / fname
        if not path.exists():
            print(f"⚠️ 跳过（不存在）: {fname}")
            continue
        print(f"\n▶ {fname}")
        n = run_sql_file(engine, path)
        print(f"  ✅ 执行 {n} 条语句")

    print("\n✅ 建视图完成")


if __name__ == "__main__":
    main()
