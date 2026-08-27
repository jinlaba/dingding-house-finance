# -*- coding: utf-8 -*-
"""
m07_组织.py — 组织透视
取 fct_办公室费用 / fct_当期收房 → 输出 JSON + xlsx
（类型热力、状态分布已按用户要求移除，不再呈现）
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, save_json, save_xlsx

def main():
    print("=== M7 组织透视 ===")

    # fct_办公室费用
    office_df = query_df("SELECT * FROM fct_办公室费用 ORDER BY 年份, 组织")
    save_xlsx(office_df, "07_办公室费用")

    # fct_当期收房
    acquire_df = query_df("SELECT * FROM fct_当期收房 ORDER BY 年份, 组织")
    save_xlsx(acquire_df, "07_当期收房")

    # 办公室费用效率（当年累计办公室费用 ÷ 当年累计收房套数，按组织对齐）
    latest_year = office_df["年份"].max()
    latest_office = office_df[office_df["年份"] == latest_year].copy()
    latest_acquire = acquire_df[acquire_df["年份"] == latest_year].copy()
    merged = latest_office.merge(latest_acquire, on="组织", how="inner")
    merged["单房办公室费用"] = merged.apply(
        lambda r: round(r["办公室费用"] / r["收房套数"], 2) if r["收房套数"] and r["收房套数"] > 0 else None,
        axis=1
    )
    merged = merged.sort_values("单房办公室费用", ascending=False)
    save_xlsx(merged, "07_办公室费用效率")
    # 公司值：年累计费用合计 ÷ 年累计收房合计（按两表都能对上的组织口径）
    company_office = round(
        merged["办公室费用"].sum() / merged["收房套数"].sum(), 2
    ) if merged["收房套数"].sum() else None

    output = {
        "办公室费用": office_df.to_dict(orient="records"),
        "当期收房": acquire_df.to_dict(orient="records"),
        "组织对比": {
            "单房办公室费用": {
                "组织值": merged[["组织", "办公室费用", "收房套数", "单房办公室费用"]].to_dict(orient="records"),
                "公司值": company_office,
                "偏好": "越低越好",
                "最新年份": latest_year,
                "说明": f"{latest_year}年累计办公室费用 ÷ {latest_year}年累计收房套数（收房年份已提取纯年份对齐）"
            }
        }
    }

    save_json(output, "m07_组织")
    print(f"  办公室费用: {len(office_df)}, 当期收房: {len(acquire_df)}")
    return output

if __name__ == "__main__":
    main()
