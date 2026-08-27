# -*- coding: utf-8 -*-
"""
m03_收支.py — 收支与瀑布
取 fct_净收支大类 / fct_月度收支汇总 / fct_大类汇总 / fct_装修收入 / fct_维修费 → 输出 JSON + xlsx
组织对比：单房维修费（组织维修支出 ÷ 在托套数，越低越好）
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, save_json, save_xlsx

def main():
    print("=== M3 收支与瀑布 ===")

    # fct_净收支大类（月份×组织×大类，随组织筛选联动）
    detail_df = query_df("SELECT * FROM fct_净收支大类 ORDER BY 月份, 组织, 大类")
    save_xlsx(detail_df, "03_净收支大类")

    # fct_月度收支汇总（按月+组织，核查用）
    summary_df = query_df("SELECT * FROM fct_月度收支汇总 ORDER BY 月份, 组织")
    save_xlsx(summary_df, "03_月度收支汇总")

    # fct_月度净收支（全公司口径，按月×大类归类，直接数据汇总表取数）
    net_df = query_df("SELECT * FROM fct_月度净收支 ORDER BY 月份, 大类")
    save_xlsx(net_df, "03_月度净收支")

    # fct_大类汇总（全公司按大类）
    cat_df = query_df("SELECT * FROM fct_大类汇总 ORDER BY 月份, 大类")
    save_xlsx(cat_df, "03_大类汇总")

    # fct_装修收入
    deco_df = query_df("SELECT * FROM fct_装修收入 ORDER BY 月份, 组织")
    save_xlsx(deco_df, "03_装修收入")

    # fct_维修费
    repair_df = query_df("SELECT * FROM fct_维修费 ORDER BY 月份, 组织")
    save_xlsx(repair_df, "03_维修费")

    # 组织对比：单房维修费（最新月份）
    latest_month = repair_df["月份"].max()
    latest_repair = repair_df[repair_df["月份"] == latest_month].copy()
    # 在托数据可能滞后于维修费月份（如维修费到 2026-07 而在托只到 2026-06），回退到最新可用在托月份
    zt_months = query_df("SELECT DISTINCT 月份 FROM fct_在托 ORDER BY 月份")
    zt_month = latest_month
    if len(zt_months):
        avail = [m for m in zt_months["月份"].tolist() if m <= latest_month]
        if avail:
            zt_month = avail[-1]
    zt_df = query_df(f"SELECT 组织机构, 在托套数 FROM fct_在托 WHERE 月份 = '{zt_month}'")
    latest_repair = latest_repair.merge(zt_df, left_on="组织", right_on="组织机构", how="left")
    # 维修支出为记账负数（支出记负），取绝对值输出为正的费用额
    latest_repair["维修支出"] = latest_repair["维修支出"].abs()
    latest_repair["单房维修费"] = latest_repair.apply(
        lambda r: round(r["维修支出"] / r["在托套数"], 2) if r["在托套数"] and r["在托套数"] > 0 else None,
        axis=1
    )
    company_repair = latest_repair["维修支出"].sum() / latest_repair["在托套数"].sum() if latest_repair["在托套数"].sum() else None
    save_xlsx(latest_repair, "03_单房维修费对比")

    # 月度收支透视（月份×组织 净额）
    pivot = summary_df.pivot_table(index="月份", columns="组织", values="净额合计", fill_value=0).reset_index()
    save_xlsx(pivot, "03_月度净额透视")

    output = {
        "月度净收支": detail_df.to_dict(orient="records"),
        "瀑布": detail_df.to_dict(orient="records"),
        "装修收入": deco_df.to_dict(orient="records"),
        "组织对比": {
            "单房维修费": {
                "组织值": latest_repair[["组织", "单房维修费"]].to_dict(orient="records"),
                "公司值": round(company_repair, 2) if company_repair else None,
                "偏好": "越低越好",
                "最新月份": latest_month,
                "在托月份": zt_month,
                "说明": f"维修支出({latest_month}，取绝对值) ÷ 在托套数({zt_month}，在托滞后时回退)"
            }
        }
    }

    save_json(output, "m03_收支")
    print(f"  净收支大类: {len(detail_df)}, 月度净收支(大类): {len(net_df)}, 大类汇总: {len(cat_df)}")
    return output

if __name__ == "__main__":
    main()
