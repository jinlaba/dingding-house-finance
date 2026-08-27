# -*- coding: utf-8 -*-
"""
m04_资金.py — 资金安全
取 fct_押金池汇总 / fct_违约损益 → 输出 JSON + xlsx
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, save_json, save_xlsx

def main():
    print("=== M4 资金安全 ===")

    # fct_押金池
    pool_df = query_df("SELECT * FROM fct_押金池 ORDER BY 月份, 账簿, 科目大类")
    save_xlsx(pool_df, "04_押金池明细")

    # fct_押金池汇总
    pool_sum_df = query_df("SELECT * FROM fct_押金池汇总 ORDER BY 月份")
    save_xlsx(pool_sum_df, "04_押金池汇总")

    # 组织级押金池（账簿→组织，随组织筛选联动）
    pool_org_df = query_df("""
        SELECT
            月份,
            账簿 AS 组织,
            SUM("期末余额-贷方金额") FILTER (WHERE 科目大类 = '租客押金') AS 租客押金,
            SUM("期末余额-借方金额") FILTER (WHERE 科目大类 = '业主押金') AS 业主押金,
            SUM("期末余额-借方金额") FILTER (WHERE 科目大类 = '现金')    AS 现金
        FROM fct_押金池
        GROUP BY 月份, 账簿
        ORDER BY 月份, 账簿
    """)
    save_xlsx(pool_org_df, "04_押金池组织")

    # fct_违约损益
    breach_df = query_df("SELECT * FROM fct_违约损益 ORDER BY 月份, 组织机构")
    save_xlsx(breach_df, "04_违约损益")

    output = {
        "押金池": pool_sum_df.to_dict(orient="records"),
        "押金池组织": pool_org_df.to_dict(orient="records"),
        "违约损益": breach_df.to_dict(orient="records")
    }

    save_json(output, "m04_资金")
    print(f"  押金池汇总: {len(pool_sum_df)}, 押金池组织: {len(pool_org_df)}, 违约损益: {len(breach_df)}")
    return output

if __name__ == "__main__":
    main()
