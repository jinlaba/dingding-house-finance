# -*- coding: utf-8 -*-
"""
m00_维度.py — 维度与元数据
取 dim_组织 / dim_月份 / dim_店面组织映射 → 输出 JSON + xlsx
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, query_list, save_json, save_xlsx, MID_DIR

def main():
    print("=== M0 维度与元数据 ===")

    # dim_组织
    orgs_df = query_df("SELECT * FROM dim_组织 ORDER BY 序号::int")
    save_xlsx(orgs_df, "00_维度_组织")

    # dim_月份
    months_df = query_df("SELECT * FROM dim_月份 ORDER BY 月份")
    save_xlsx(months_df, "00_维度_月份")

    # dim_店面组织映射
    map_df = query_df("SELECT * FROM dim_店面组织映射 ORDER BY 组织机构, 店面")
    save_xlsx(map_df, "00_维度_店面映射")

    # 组织列表（运营组织）
    orgs = orgs_df[orgs_df["是否运营组织"] == 1]["组织机构"].unique().tolist()

    # 月份列表
    months = months_df["月份"].tolist()

    # 店面→组织映射
    org_shop_map = {}
    for _, row in map_df.iterrows():
        org = row["组织机构"]
        shop = row["店面"]
        if org not in org_shop_map:
            org_shop_map[org] = []
        org_shop_map[org].append(shop)

    # 检查在托房源/数据汇总表中是否有组织表里没有的店面
    # 组织表中没有的组织需要在看板/核查中给出提示
    all_orgs_in_data = query_list("SELECT DISTINCT 组织 FROM 数据汇总表 WHERE 组织 IS NOT NULL AND 组织 != '' ORDER BY 组织")
    all_orgs_in_data = [r["组织"] for r in all_orgs_in_data]
    missing_orgs = [o for o in all_orgs_in_data if o not in orgs]

    output = {
        "orgs": orgs,
        "months": months,
        "org_shop_map": org_shop_map,
        "missing_orgs": missing_orgs,
        "missing_orgs_alert": f"数据汇总表中发现 {len(missing_orgs)} 个组织表里没有的组织：{', '.join(missing_orgs)}" if missing_orgs else ""
    }

    save_json(output, "m00_维度")
    print(f"  组织数: {len(orgs)}, 月份数: {len(months)}, 缺失组织: {len(missing_orgs)}")
    return output

if __name__ == "__main__":
    main()
