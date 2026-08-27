# -*- coding: utf-8 -*-
"""
m08_说明.py — 数据说明
取 fct_血缘 / fct_未分类占比 → 输出 JSON + xlsx
模块名称、指标说明从PG数据库产生，通俗易懂给领导看
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import query_df, save_json, save_xlsx

# 模块说明（通俗版，供领导理解）
MODULE_DESC = {
    "M0 维度": "看板左上角的筛选器：选哪个分公司、看哪个月份",
    "M1 规模": "公司在管多少套房、每月收进来多少、租出去多少、退了多少",
    "M2 出租率": "房子租得快不快：出租率、空置损失、超60天还没租出去的房子占比",
    "M3 收支": "这个月收了多少钱、花了多少钱、净赚多少，钱花在哪些大类",
    "M4 资金": "押金池够不够厚、违约退房赚了多少",
    "M5 财务": "按财务口径的利润表、毛利率、净利率",
    "M6 利润": "每套房赚不赚钱：已实现的利润 + 未来还能赚的剩余价值",
    "M7 组织": "各分公司多维度对比：收退比、单房租差、单房净利、单房维修费、毛利率净利率等",
    "M8 数据说明": "本页每个数字的来源和计算方式",
}

def main():
    print("=== M8 数据说明 ===")

    # fct_血缘
    lineage_df = query_df("SELECT * FROM fct_血缘 ORDER BY 视图名, 字段名")
    save_xlsx(lineage_df, "08_血缘")

    # fct_未分类占比
    unclass_df = query_df("SELECT * FROM fct_未分类占比 ORDER BY 月份")
    save_xlsx(unclass_df, "08_未分类占比")

    # 模块说明（从PG数据库产生 + 通俗说明）
    modules = []
    for key, desc in MODULE_DESC.items():
        modules.append({
            "模块": key,
            "一句话说明": desc,
            "数据来源": "PostgreSQL「顶鼎」库视图",
            "计算方式": "见 fct_血缘 视图"
        })

    output = {
        "模块说明": modules,
        "未分类占比": unclass_df.to_dict(orient="records"),
        "免责": "本看板数据来源于公司运营系统与财务系统，仅供内部经营分析参考。"
    }

    save_json(output, "m08_说明")
    print(f"  血缘字段: {len(lineage_df)}, 未分类占比: {len(unclass_df)}")
    return output

if __name__ == "__main__":
    main()
