# -*- coding: utf-8 -*-
"""
m02_出租率.py — 出租率与空置
取 fct_出租率 / fct_空置损失 / fct_空置60 → 输出 JSON + xlsx
组织对比：空置损失占比（越低越好）、超60天空置占比（越低越好）
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, save_json, save_xlsx

def main():
    print("=== M2 出租率与空置 ===")

    # fct_出租率
    rate_df = query_df("SELECT * FROM fct_出租率 ORDER BY 月份, 组织机构")
    save_xlsx(rate_df, "02_出租率趋势")

    # fct_空置损失
    loss_df = query_df("SELECT * FROM fct_空置损失 ORDER BY 来源文件 DESC, 组织机构")
    save_xlsx(loss_df, "02_空置损失")

    # fct_空置60
    v60_df = query_df("SELECT * FROM fct_空置60 ORDER BY 超60占比 DESC")
    save_xlsx(v60_df, "02_空置60")

    # 出租率透视（月份×组织）
    rate_pivot = rate_df.pivot_table(index="月份", columns="组织机构", values="出租率", fill_value=0).reset_index()
    save_xlsx(rate_pivot, "02_出租率透视")

    # 组织对比：空置损失占比（最新快照）
    latest_source = loss_df["来源文件"].max()
    latest_loss = loss_df[loss_df["来源文件"] == latest_source].copy()
    total_loss = latest_loss["空置损失合计"].sum()
    latest_loss["空置损失占比"] = latest_loss["空置损失合计"] / total_loss if total_loss else None
    save_xlsx(latest_loss, "02_空置损失占比对比")

    # 组织对比：超60天空置占比
    company_v60 = v60_df["超60套数"].sum() / v60_df["总套数"].sum() if v60_df["总套数"].sum() else None

    output = {
        "出租率趋势": rate_pivot.to_dict(orient="list"),
        "空置损失": loss_df.to_dict(orient="records"),
        "空置60": v60_df.to_dict(orient="records"),
        "组织对比": {
            "空置损失占比": {
                "组织值": latest_loss[["组织机构", "空置损失占比"]].to_dict(orient="records"),
                "公司值": 1.0,
                "偏好": "越低越好",
                "最新快照": latest_source
            },
            "超60天空置占比": {
                "组织值": v60_df[["组织机构", "超60占比"]].to_dict(orient="records"),
                "公司值": round(company_v60, 4) if company_v60 else None,
                "偏好": "越低越好"
            }
        }
    }

    save_json(output, "m02_出租率")
    print(f"  出租率记录: {len(rate_df)}, 空置损失记录: {len(loss_df)}, 空置60记录: {len(v60_df)}")
    return output

if __name__ == "__main__":
    main()
