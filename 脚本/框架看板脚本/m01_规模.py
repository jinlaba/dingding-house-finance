# -*- coding: utf-8 -*-
"""
m01_规模.py — 规模与增长
取 fct_在托 / fct_收出退 / fct_业主退房 / fct_收房类型 → 输出 JSON + xlsx
口径（用户确认版）：
  收房     = 收房统计表（业主口径，按月）
  出房     = 新租房源（租客口径，按月）
  租客退房 = 租客已退房登记日期（租客口径，按月）
  业主退房 = 全房源最新快照按业主租期到期倒推（业主口径，按月，历史月偏低、最新月最准）
组织对比：收退比（当月收房 ÷ 当月业主退房，越高越好；收出房比无数据，按用户要求改为与业主退房对比）
"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pandas as pd
from db import query_df, save_json, save_xlsx, month_over_month

def main():
    print("=== M1 规模与增长 ===")

    # fct_在托
    zt_df = query_df("SELECT * FROM fct_在托 ORDER BY 月份, 组织机构")
    save_xlsx(zt_df, "01_在托趋势")

    # fct_收出退（收房/出房/租客退房，按月）
    cot_df = query_df("SELECT * FROM fct_收出退 ORDER BY 月份, 组织机构")
    save_xlsx(cot_df, "01_收出退")

    # fct_业主退房（业主口径，按月，来自最新快照业主租期到期倒推）
    own_exit_df = query_df("SELECT * FROM fct_业主退房 ORDER BY 月份, 组织机构")
    save_xlsx(own_exit_df, "01_业主退房")

    # fct_收房类型
    type_df = query_df("SELECT * FROM fct_收房类型 ORDER BY 套数 DESC")
    save_xlsx(type_df, "01_收房类型")

    # 组织对比：收退比 = 当月收房 ÷ 当月业主退房（收出房比无数据，按用户要求改为与业主退房对比）
    # 月份基准：有收房数据的最新月份；若该月公司总收房明显偏低（< 前3月均值的30%），
    #           视为收房统计表录入滞后（如8月只录1套），回退用上一个完整月
    acq_months = cot_df[cot_df["收房"] > 0]["月份"].unique().tolist()
    monthly_acq = cot_df.groupby("月份")["收房"].sum()
    if acq_months:
        base_month = max(acq_months)
        prior = sorted([m for m in monthly_acq.index.tolist() if m < base_month])[-3:]
        if prior:
            avg3 = float(monthly_acq[[m for m in prior if m in monthly_acq.index]].mean())
            if avg3 > 0 and float(monthly_acq.get(base_month, 0)) < avg3 * 0.3 and len(prior) >= 2:
                base_month = prior[-1]
    else:
        base_month = None
    ratio_rows = []
    company_ratio = None
    if base_month:
        acq = cot_df[cot_df["月份"] == base_month].groupby("组织机构")["收房"].sum()
        ext = own_exit_df[own_exit_df["月份"] == base_month].groupby("组织机构")["业主退房套数"].sum()
        orgs = sorted(set(acq.index) | set(ext.index))
        for org in orgs:
            a = float(acq.get(org, 0))
            e = float(ext.get(org, 0))
            ratio_rows.append({
                "组织机构": org,
                "当月收房": a,
                "业主退房": e,
                "收退比": round(a / e, 2) if e > 0 else None,
            })
        total_a = float(acq.sum())
        total_e = float(ext.sum())
        company_ratio = round(total_a / total_e, 2) if total_e > 0 else None
    ratio_df = pd.DataFrame(ratio_rows) if ratio_rows else pd.DataFrame()
    save_xlsx(ratio_df, "01_收退比对比")

    # 在托趋势透视（月份×组织）
    zt_pivot = zt_df.pivot_table(index="月份", columns="组织机构", values="在托套数", fill_value=0).reset_index()
    save_xlsx(zt_pivot, "01_在托透视")

    output = {
        "在托趋势": zt_pivot.to_dict(orient="list"),
        "收出退": cot_df.to_dict(orient="records"),
        "业主退房": own_exit_df.to_dict(orient="records"),
        "收房类型": type_df.to_dict(orient="records"),
        "组织对比": {
            "收退比": {
                "组织值": ratio_rows,
                "公司值": company_ratio,
                "偏好": "越高越好",
                "最新月份": base_month,
                "说明": f"当月收房 ÷ 当月业主退房，基准月 {base_month}（业主退房为快照倒推口径；收房录入滞后时自动回退上一完整月）"
            }
        }
    }

    save_json(output, "m01_规模")
    print(f"  在托记录: {len(zt_df)}, 收出退记录: {len(cot_df)}, 业主退房记录: {len(own_exit_df)}, 收房类型: {len(type_df)}")
    return output

if __name__ == "__main__":
    main()
