# -*- coding: utf-8 -*-
"""
m06_利润.py — 利润与价值（基于房源利润预估表视图重建）
数据链：数据汇总表(实际收支) + 剩余价值表(未来利润,缺失自动倒推) + 房源收出房价 + 出租部提成性质
每套房全周期利润 = 实际净收支 + 剩余价值 − 运营成本(130元/月) − 出房提成 − 出租率调整(收房价×8%/年)
组织对比：单房月租差、单房月净利、单房全周期利润（取自 fct_利润预估汇总）
后端组织（出租子公司、装修子公司、家服）不参与单房全周期利润比较（用户确认，2026-08-26）
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, save_json, save_xlsx

# 后端组织：不参与单房全周期利润比较（前端运营组织才有可比性）
BACKEND_ORGS = ["出租子公司", "装修子公司", "家服"]

def main():
    print("=== M6 利润与价值 ===")

    # fct_已实现利润（月度×组织）
    realized_df = query_df("SELECT * FROM fct_已实现利润 ORDER BY 月份, 组织")
    save_xlsx(realized_df, "06_已实现利润")

    # fct_利润预估汇总（单房全周期利润，按组织）
    estimate_df = query_df("SELECT * FROM fct_利润预估汇总 ORDER BY 最终房源价值合计 DESC")
    save_xlsx(estimate_df, "06_利润预估汇总")

    # 房源利润预估表 样例（Top 100 最终价值，供审核）
    detail_df = query_df("""
        SELECT 物业地址, 组织, 房源类型, 收房价, 出房价, 性质,
               实际净收支, 剩余月数, 剩余价值, 剩余价值来源
        FROM 房源利润预估表
        WHERE 剩余价值 IS NOT NULL
        ORDER BY 实际净收支 + 剩余价值 DESC
        LIMIT 100
    """)
    save_xlsx(detail_df, "06_利润预估明细Top100")

    # 剩余价值来源统计（报表 vs 倒推测算）
    src_df = query_df("""
        SELECT 组织, 剩余价值来源, COUNT(*) AS 套数
        FROM 房源利润预估表
        WHERE 剩余价值来源 IS NOT NULL
        GROUP BY 组织, 剩余价值来源
        ORDER BY 组织, 剩余价值来源
    """)
    save_xlsx(src_df, "06_剩余价值来源")

    # fct_租差分布
    diff_df = query_df("SELECT * FROM fct_租差分布")
    save_xlsx(diff_df, "06_租差分布")

    # fct_类型利润
    type_df = query_df("SELECT * FROM fct_类型利润 ORDER BY 月份, 组织, 房源类型")
    save_xlsx(type_df, "06_类型利润")

    # fct_利润瀑布（月份×组织）
    waterfall_df = query_df("SELECT * FROM fct_利润瀑布 ORDER BY 月份")
    save_xlsx(waterfall_df, "06_利润瀑布")

    # 组织对比：单房月租差（最新快照日租金差按组织）
    diff_org_df = query_df("""
        SELECT
            m.组织机构,
            COUNT(*) AS 套数,
            ROUND(AVG(NULLIF(d.租差,'')::numeric), 2) AS 平均租差
        FROM 日租金差 d
        JOIN dim_店面组织映射 m ON d.店面 = m.店面
        WHERE d.来源文件 = (SELECT MAX(来源文件) FROM 日租金差)
          AND d.租差 ~ '^-?[0-9]+(\\.[0-9]+)?$'
        GROUP BY m.组织机构
        ORDER BY 平均租差 DESC
    """)
    save_xlsx(diff_org_df, "06_单房月租差对比")
    company_diff = diff_org_df["平均租差"].mean() if len(diff_org_df) else None

    # 组织对比：单房月净利（已实现利润 ÷ 在托套数）
    latest_month = realized_df["月份"].max()
    latest_realized = realized_df[realized_df["月份"] == latest_month].copy()
    # 在托数据可能滞后于利润数据（如利润已到 2026-07 而在托只到 2026-06），回退到最新可用在托月份
    zt_months = query_df("SELECT DISTINCT 月份 FROM fct_在托 ORDER BY 月份")
    zt_month = latest_month
    if len(zt_months):
        avail = [m for m in zt_months["月份"].tolist() if m <= latest_month]
        if avail:
            zt_month = avail[-1]
    zt_df = query_df(f"SELECT 组织机构, 在托套数 FROM fct_在托 WHERE 月份 = '{zt_month}'")
    zt_df = zt_df.rename(columns={"组织机构": "组织"})
    latest_realized = latest_realized.merge(zt_df, on="组织", how="left")
    latest_realized["单房月净利"] = latest_realized.apply(
        lambda r: round(r["已实现利润"] / r["在托套数"], 2) if r["在托套数"] and r["在托套数"] > 0 else None,
        axis=1
    )
    save_xlsx(latest_realized, "06_单房月净利对比")

    # 组织对比：单房全周期利润（fct_利润预估汇总，含三项扣减）
    # 后端组织（出租子公司、装修子公司、家服）不参与比较，前端运营组织才有可比性
    full_cycle = estimate_df[~estimate_df["组织"].isin(BACKEND_ORGS)][
        ["组织", "房源数", "倒推测算套数", "实际净收支合计", "剩余价值合计",
         "运营成本合计", "出房提成合计", "出租率调整合计", "最终房源价值合计", "单房全周期利润"]].copy()
    fc = estimate_df[~estimate_df["组织"].isin(BACKEND_ORGS)]
    company_full = round(
        fc["最终房源价值合计"].sum() / fc["房源数"].sum(), 2
    ) if fc["房源数"].sum() else None

    output = {
        "已实现利润": realized_df.to_dict(orient="records"),
        "利润预估汇总": estimate_df.to_dict(orient="records"),
        "剩余价值来源": src_df.to_dict(orient="records"),
        "租差分布": diff_df.to_dict(orient="records"),
        "类型利润": type_df.to_dict(orient="records"),
        "利润瀑布": waterfall_df.to_dict(orient="records"),
        "组织对比": {
            "单房月租差": {
                "组织值": diff_org_df.to_dict(orient="records"),
                "公司值": round(company_diff, 2) if company_diff else None,
                "偏好": "越高越好"
            },
            "单房月净利": {
                "组织值": latest_realized[["组织", "单房月净利"]].to_dict(orient="records"),
                "公司值": round(latest_realized["已实现利润"].sum() / latest_realized["在托套数"].sum(), 2) if latest_realized["在托套数"].sum() else None,
                "偏好": "越高越好",
                "最新月份": latest_month
            },
            "单房全周期利润": {
                "组织值": full_cycle.to_dict(orient="records"),
                "公司值": company_full,
                "偏好": "越高越好",
                "说明": "实际净收支+剩余价值−运营成本−出房提成−出租率调整，剩余价值缺失房源按租差×剩余月数倒推；后端组织（出租子公司、装修子公司、家服）不参与比较"
            }
        }
    }

    save_json(output, "m06_利润")
    print(f"  已实现利润: {len(realized_df)}, 利润预估组织: {len(estimate_df)}（比较 {len(full_cycle)}）")
    return output

if __name__ == "__main__":
    main()
