# -*- coding: utf-8 -*-
"""
m05_财务.py — 财务三表（法定格式，精简关键行）
=================================================
数据源原始 Excel（利润/资产/现金流量）报表项目行序即法定顺序，
但 PostgreSQL 表物理行序不可靠，故在此硬编码标准顺序 + 精简关键行。

三表口径：
  • 利润表 / 现金流量表列名带「(本年累计数)」= 本年累计
  • 资产负债表列名带「(期末数)」= 时点余额
  • 单月金额 = 本期累计 − 上期累计（跨年首月不减去去年12月）

输出 JSON:
  利润表 / 资产负债表 / 现金流量表  → 有序精简行式（含累计、单月、序号、分组）
  财务指标 / 组织对比（毛利率净利率）
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pandas as pd
from db import query_df, save_json, save_xlsx

# 后端组织：财务报表列与组织对比中不呈现（用户确认，2026-08-26）
BACKEND_ORGS = ["出租子公司", "装修子公司", "家服"]
# 正常（前端运营）组织列的展示顺序
ORG_COL_ORDER = [
    "总公司新毛坯三", "雨花分公司", "高奢精空子公司", "业务子公司", "焕新子公司",
    "精装托管二店", "精装托管三店", "老店面（新毛坯2）", "装修代售店", "家装业务部",
]

# ---------------- 三表标准顺序 + 精简关键行 ----------------
# 每项：(报表项目名, 所属区块/分组)
# 同名项目（如现金流量表的「现金流入/现金流出」在经营/投资/筹资下各有一次）
# 靠「区块」区分：先按每期行序用分节标题行切分区块，再把行归入当前区块。
# 分节标题行（区块切换行）本身不渲染金额，作为「部分标题」。

PL_ORDER = [
    ("一、营业收入", "收入"),
    ("二、营业成本", "成本"),
    ("三、税金及附加", "税金"),
    ("四、销售费用", "费用"),
    ("五、财务费用", "费用"),
    ("六、营业利润（亏损以“-”号填列）", "利润"),
    ("减：所得税费用", "利润"),
    ("加：营业外收入", "利润"),
    ("减：营业外支出", "利润"),
    ("七、净利润（净亏损以“-”号填列）", "利润"),
    ("减：以前年度损益调整", "利润"),
    ("八、综合利润（亏损以“-”号填列）", "利润"),
    ("加：期初未分配利润", "利润"),
    ("减：本期利润分配", "利润"),
    ("九、期末未分配利润", "利润"),
]

BS_ORDER = [
    ("流动资产：",   "资产"),
    ("货币资金",     "资产"),
    ("应收账款",     "资产"),
    ("存货",         "资产"),
    ("流动资产合计", "资产"),
    ("非流动资产：", "资产"),
    ("固定资产",     "资产"),
    ("非流动资产合计", "资产"),
    ("资产总计",      "资产"),
    ("流动负债：",    "负债"),
    ("短期借款",      "负债"),
    ("应付账款",      "负债"),
    ("应付职工薪酬",  "负债"),
    ("应交税费",      "负债"),
    ("流动负债合计",  "负债"),
    ("非流动负债：",  "负债"),
    ("非流动负债合计", "负债"),
    ("负债合计",      "负债"),
    ("所有者权益（或股东权益）：", "权益"),
    ("实收资本（或股本）", "权益"),
    ("盈余公积",      "权益"),
    ("未分配利润",    "权益"),
    ("所有者权益（或股东权益）合计", "权益"),
    ("负债和所有者权益（或股东权益）总计", "权益"),
]

CF_ORDER = [
    ("经营活动产生的现金流量", "经营"),
    ("工程款收入",   "经营"),
    ("房租物业收入", "经营"),
    ("押金类收入",   "经营"),
    ("现金流入",     "经营"),
    ("工程类支出",   "经营"),
    ("房租物业支出", "经营"),
    ("押金类支出",   "经营"),
    ("现金流出",     "经营"),
    ("经营活动产生的现金流量净额", "经营"),
    ("投资活动产生的现金流量", "投资"),
    ("现金流入", "投资"),
    ("现金流出", "投资"),
    ("投资活动产生的现金流量净额", "投资"),
    ("筹资活动产生的现金流量", "筹资"),
    ("吸收投资收到的现金", "筹资"),
    ("取得借款收到的现金", "筹资"),
    ("现金流入", "筹资"),
    ("偿还入股本金支付的现金", "筹资"),
    ("分配利润支付的现金", "筹资"),
    ("现金流出", "筹资"),
    ("筹资活动产生的现金流量净额", "筹资"),
    ("现金及现金等价物净增加额", "合计"),
    ("加：期初现金及现金等价物余额", "合计"),
    ("六、期末现金及现金等价物余额", "合计"),
]

# 分节标题行（区块切换行）：不渲染金额，作为「部分标题」
SECTION_ITEMS = {
    "流动资产：", "非流动资产：", "流动负债：", "非流动负债：",
    "所有者权益（或股东权益）：",
    "经营活动产生的现金流量", "投资活动产生的现金流量",
    "筹资活动产生的现金流量",
    # 不在精简清单内的分节标题（如「汇率变动产生的现金流量」）也重置区块，
    # 避免其下同名行（现金流入/现金流出）被错误归入上一区块
    "汇率变动产生的现金流量",
}


def _section_for_title(name, key_map_items):
    """标题行 → 所属区块（用于上下文切换）"""
    for n, sec in key_map_items:
        if n == name and name in SECTION_ITEMS:
            return sec
    return None


def build_stmt(key_order, view_name, is_accum=True):
    """构建一行式有序精简报表。
    view_name: fct 视图名
    is_accum: 是否按累计差分出单月金额（资产负债表为时点，单月=本期）
    返回：有序列表 [{报表项目, 列名, 来源文件, 金额, 单月金额, ord, 分组, 是标题}]
    """
    df = query_df(f"SELECT * FROM {view_name} WHERE 报表项目 IS NOT NULL AND 报表项目 != ''")
    if df.empty:
        return []

    key_map_items = list(key_order)
    # 唯一键允许同名不同区块：(项目名, 区块) → ord
    key_index = {}
    name_sections = {}  # 项目名 → 候选区块集合
    for i, (n, sec) in enumerate(key_map_items):
        key_index[(n, sec)] = i
        name_sections.setdefault(n, set()).add(sec)

    df["来源文件"] = df["来源文件"].astype(str)
    df["金额"] = pd.to_numeric(df["金额"], errors="coerce")

    # 第一步：按「期 × 物理行序」给每行打区块 / 判定是否为标题行
    records = []  # {区块, 报表项目, 列名, 来源文件, 金额, 是标题, ord}
    periods = sorted(df["来源文件"].unique())
    for period in periods:
        sub = df[df["来源文件"] == period]
        cur_sec = None
        for _, raw in sub.iterrows():
            name = raw["报表项目"]
            col = raw["列名"]
            acc = raw["金额"] if pd.notna(raw["金额"]) else None
            if name in SECTION_ITEMS:
                # 分节标题：切换区块。不在精简清单内的分节标题（如「汇率变动产生的现金流量」）
                # 只重置区块（置 None），不输出标题行，避免其下同名行被错误归入上一区块
                sec = _section_for_title(name, key_map_items)
                cur_sec = sec
                if sec is not None:
                    records.append({
                        "区块": sec, "报表项目": name, "列名": col,
                        "来源文件": period, "金额": None, "单月金额": None,
                        "是标题": True,
                    })
                continue
            # 普通行：归入当前区块；当前区块为空时回退到该项目的唯一区块
            secs = name_sections.get(name, set())
            match_sec = cur_sec if (cur_sec is not None and cur_sec in secs) else (next(iter(secs)) if len(secs) == 1 else None)
            idx = key_index.get((name, match_sec))
            if idx is None:
                # 不在精简清单内，跳过
                continue
            records.append({
                "区块": match_sec, "报表项目": name, "列名": col,
                "来源文件": period, "金额": acc, "单月金额": None,
                "是标题": False,
            })

    # 第二步：跨期累计差分出单月（按 区块×项目×列名 分组）
    grouped = {}
    for rec in records:
        gk = (rec["区块"], rec["报表项目"], rec["列名"])
        grouped.setdefault(gk, []).append(rec)
    prev_map = {}  # gk -> (上期累计, 上期来源文件)
    for gk, recs in grouped.items():
        recs.sort(key=lambda r: r["来源文件"])
        prev_acc = None
        prev_period = None
        for rec in recs:
            acc = rec["金额"]
            if is_accum and prev_period is not None:
                cur_year = rec["来源文件"][:4]
                prev_year = prev_period[:4]
                if cur_year != prev_year:
                    monthly = acc
                elif acc is not None and prev_acc is not None:
                    monthly = acc - prev_acc
                else:
                    monthly = None
            else:
                monthly = acc
            rec["单月金额"] = monthly
            prev_acc = acc
            prev_period = rec["来源文件"]

    # 第三步：组装输出（带 ord、分组、is_title）
    out = []
    for rec in records:
        if rec["是标题"]:
            ordv = key_index[(rec["报表项目"], rec["区块"])]
            out.append({
                "报表项目": rec["报表项目"], "列名": rec["列名"],
                "来源文件": rec["来源文件"], "金额": None, "单月金额": None,
                "ord": int(ordv), "分组": rec["区块"], "是标题": True,
            })
        else:
            ordv = key_index[(rec["报表项目"], rec["区块"])]
            acc = rec["金额"]
            monthly = rec["单月金额"]
            out.append({
                "报表项目": rec["报表项目"], "列名": rec["列名"],
                "来源文件": rec["来源文件"],
                "金额": round(acc, 2) if acc is not None else None,
                "单月金额": round(monthly, 2) if monthly is not None else None,
                "ord": int(ordv), "分组": rec["区块"], "是标题": False,
            })
    return out


def get_amount(rows, item, period, col=None):
    """取某报表项目某期次金额（可选列名）"""
    r = [x for x in rows if item in str(x["报表项目"]) and str(x["来源文件"]) == str(period)]
    if col:
        r = [x for x in r if x["列名"] == col]
    if not r:
        return None
    return sum(x["金额"] for x in r if x["金额"] is not None)


def get_single_amount(rows, item, period, col=None):
    r = [x for x in rows if item in str(x["报表项目"]) and str(x["来源文件"]) == str(period)]
    if col:
        r = [x for x in r if x["列名"] == col]
    if not r:
        return None
    return sum(x["单月金额"] for x in r if x["单月金额"] is not None)


def calc_metrics_for_col(pl_rows, bs_rows, col):
    """按列名计算财务指标（利润表本年累计 + 资产负债表期末数）"""
    cr = [x for x in pl_rows if x["列名"] == col]
    if not cr:
        return []
    periods = sorted(set(x["来源文件"] for x in cr))
    latest = periods[-1]
    prev = periods[-2] if len(periods) > 1 else None
    ly = None
    if latest:
        y = str(int(latest[:4]) - 1)
        m = latest[5:7]
        cand = [p for p in periods if p[:4] == y and p[5:7] == m]
        ly = cand[0] if cand else None

    rev = get_amount(cr, "营业收入", latest)
    rev_prev = get_amount(cr, "营业收入", prev) if prev else None
    rev_ly = get_amount(cr, "营业收入", ly) if ly else None
    cost = get_amount(cr, "营业成本", latest)
    net = get_amount(cr, "净利润", latest)
    net_prev = get_amount(cr, "净利润", prev) if prev else None
    net_ly = get_amount(cr, "净利润", ly) if ly else None
    op = get_amount(cr, "营业利润", latest)
    sale = get_amount(cr, "销售费用", latest) or 0
    fin = get_amount(cr, "财务费用", latest) or 0

    # 资产负债表（期末数，时点；用精确匹配避免「负债合计」误匹配「流动负债合计」）
    br = [x for x in bs_rows if x["列名"] == col]
    bs_periods = sorted(set(x["来源文件"] for x in br))
    bs_latest = bs_periods[-1] if bs_periods else None

    def bs_amt(item):
        if not bs_latest:
            return None
        r = [x for x in br if x["报表项目"] == item and x["来源文件"] == bs_latest]
        vals = [x["金额"] for x in r if x["金额"] is not None]
        return sum(vals) if vals else None

    assets = bs_amt("资产总计")
    liabilities = bs_amt("负债合计")
    equity = bs_amt("所有者权益（或股东权益）合计")
    cur_assets = bs_amt("流动资产合计")
    cur_liab = bs_amt("流动负债合计")
    cash = bs_amt("货币资金")

    def ratio(a, b):
        if a is None or b is None or b == 0:
            return None
        return round(a / b, 4)

    def chg(cur, base):
        if cur is None or base is None or base == 0:
            return None
        return round(cur / base - 1, 4)

    return [
        {"指标": "毛利率", "分类": "盈利能力", "公式": "(营业收入-营业成本)/营业收入", "列名": col, "值": ratio(rev - cost if rev is not None and cost is not None else None, rev)},
        {"指标": "净利率", "分类": "盈利能力", "公式": "净利润/营业收入", "列名": col, "值": ratio(net, rev)},
        {"指标": "营业利润率", "分类": "盈利能力", "公式": "营业利润/营业收入", "列名": col, "值": ratio(op, rev)},
        {"指标": "成本率", "分类": "盈利能力", "公式": "营业成本/营业收入", "列名": col, "值": ratio(cost, rev)},
        {"指标": "销售费用率", "分类": "盈利能力", "公式": "销售费用/营业收入", "列名": col, "值": ratio(sale, rev)},
        {"指标": "财务费用率", "分类": "盈利能力", "公式": "财务费用/营业收入", "列名": col, "值": ratio(fin, rev)},
        {"指标": "收入环比", "分类": "成长能力", "公式": "本期营业收入/上月-1", "列名": col, "值": chg(rev, rev_prev)},
        {"指标": "收入同比", "分类": "成长能力", "公式": "本期营业收入/去年同期-1", "列名": col, "值": chg(rev, rev_ly)},
        {"指标": "净利润环比", "分类": "成长能力", "公式": "本期净利润/上月-1", "列名": col, "值": chg(net, net_prev)},
        {"指标": "净利润同比", "分类": "成长能力", "公式": "本期净利润/去年同期-1", "列名": col, "值": chg(net, net_ly)},
        {"指标": "资产负债率", "分类": "偿债能力", "公式": "负债合计/资产总计", "列名": col, "值": ratio(liabilities, assets)},
        {"指标": "流动比率", "分类": "偿债能力", "公式": "流动资产合计/流动负债合计", "列名": col, "值": ratio(cur_assets, cur_liab)},
        {"指标": "现金比率", "分类": "偿债能力", "公式": "货币资金/流动负债合计", "列名": col, "值": ratio(cash, cur_liab)},
        {"指标": "净资产收益率(ROE)", "分类": "回报能力", "公式": "净利润/所有者权益合计", "列名": col, "值": ratio(net, equity)},
        {"指标": "总资产收益率(ROA)", "分类": "回报能力", "公式": "净利润/资产总计", "列名": col, "值": ratio(net, assets)},
    ]


def main():
    print("=== M5 财务三表（法定格式·精简） ===")

    pl_rows = build_stmt(PL_ORDER, "fct_利润表", is_accum=True)
    bs_rows = build_stmt(BS_ORDER, "fct_资产负债表", is_accum=False)
    cf_rows = build_stmt(CF_ORDER, "fct_现金流量表", is_accum=True)

    pl_df = pd.DataFrame(pl_rows)
    bs_df = pd.DataFrame(bs_rows)
    cf_df = pd.DataFrame(cf_rows)

    save_xlsx(pl_df, "05_利润表")
    save_xlsx(bs_df, "05_资产负债表")
    save_xlsx(cf_df, "05_现金流量表")

    # 财务指标（按列名）
    ind_list = []
    if not pl_df.empty:
        for col in pl_df["列名"].unique():
            ind_list.extend(calc_metrics_for_col(pl_rows, bs_rows, col))
    ind_df = pd.DataFrame(ind_list)
    save_xlsx(ind_df, "05_财务指标")

    # 组织对比：毛利率/净利率（最新期，合并数=基准；后端组织不参与）
    org_compare = []
    company_margin = company_net = None
    if not pl_df.empty:
        latest_period = sorted(pl_df["来源文件"].unique())[-1]
        rev_df = [x for x in pl_rows if "营业收入" in x["报表项目"] and x["来源文件"] == latest_period]
        cost_df = [x for x in pl_rows if "营业成本" in x["报表项目"] and x["来源文件"] == latest_period]
        net_df = [x for x in pl_rows if "净利润" in x["报表项目"] and x["来源文件"] == latest_period]
        for col in pl_df["列名"].unique():
            if col == "合并数" or col in BACKEND_ORGS:
                continue
            rev = sum(x["金额"] for x in rev_df if x["列名"] == col and x["金额"] is not None)
            cost = sum(x["金额"] for x in cost_df if x["列名"] == col and x["金额"] is not None)
            net = sum(x["金额"] for x in net_df if x["列名"] == col and x["金额"] is not None)
            org_compare.append({
                "组织": col,
                "毛利率": round((rev - cost) / rev, 4) if rev else None,
                "净利率": round(net / rev, 4) if rev else None
            })
        org_compare.sort(key=lambda r: ORG_COL_ORDER.index(r["组织"]) if r["组织"] in ORG_COL_ORDER else 99)
        rev_m = sum(x["金额"] for x in rev_df if x["列名"] == "合并数" and x["金额"] is not None)
        cost_m = sum(x["金额"] for x in cost_df if x["列名"] == "合并数" and x["金额"] is not None)
        net_m = sum(x["金额"] for x in net_df if x["列名"] == "合并数" and x["金额"] is not None)
        company_margin = round((rev_m - cost_m) / rev_m, 4) if rev_m else None
        company_net = round(net_m / rev_m, 4) if rev_m else None

    compare_df = pd.DataFrame(org_compare)
    save_xlsx(compare_df, "05_毛利率净利率对比")

    # 正常组织列（合并数 + 前端运营组织，排除后端组织），供报表渲染使用
    all_cols = list(pl_df["列名"].unique()) if not pl_df.empty else []
    org_cols = [c for c in all_cols if c not in BACKEND_ORGS]
    org_cols.sort(key=lambda c: (0 if c == "合并数" else 1,
                                 ORG_COL_ORDER.index(c) if c in ORG_COL_ORDER else 99))

    output = {
        "利润表": pl_rows,
        "资产负债表": bs_rows,
        "现金流量表": cf_rows,
        "财务指标": ind_list,
        "组织列": org_cols,
        "组织对比": {
            "毛利率净利率": {
                "组织值": org_compare,
                "公司毛利率": company_margin,
                "公司净利率": company_net,
                "偏好": "越高越好",
                "说明": "后端组织（出租子公司、装修子公司、家服）不参与比较"
            }
        }
    }

    save_json(output, "m05_财务")
    print(f"  利润表: {len(pl_rows)}, 资产负债表: {len(bs_rows)}, 现金流量表: {len(cf_rows)}, 财务指标: {len(ind_list)}")
    return output


if __name__ == "__main__":
    main()