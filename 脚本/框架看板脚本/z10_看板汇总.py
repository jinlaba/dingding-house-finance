# -*- coding: utf-8 -*-
"""
z10_看板汇总.py — 汇总器（唯一入口）
职责：只做合并，不做业务计算
  1. 依次执行各模块 m00~m08（取数+输出JSON+xlsx）
  2. 读所有 m*.json 合并成 const DATA
  3. 生成 00_取数说明.xlsx（全链路索引）
  4. 注入 HTML 生成 顶鼎运营驾驶舱.html

用法：
  python z10_看板汇总.py            # 全量跑
  python z10_看板汇总.py --only m03  # 只重跑 m03 模块
"""
import sys, pathlib, json, argparse, subprocess, datetime

SCRIPT_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
MID_DIR = SCRIPT_DIR / "中间数据"
MID_DIR.mkdir(exist_ok=True)

# 模块执行顺序（M0 维度是基础，必须先跑）
MODULES = [
    "m00_维度",
    "m01_规模",
    "m02_出租率",
    "m03_收支",
    "m04_资金",
    "m05_财务",
    "m06_利润",
    "m07_组织",
    "m08_说明",
]

# HTML 模板路径（与看板同目录）
HTML_TEMPLATE = SCRIPT_DIR / "顶鼎运营驾驶舱_模板.html"
# 输出看板路径（与现有 v8 看板同位置，用户直接打开）
HTML_OUTPUT = pathlib.Path(r"G:\obsidian\胡多多\1projects\顶鼎\顶鼎运营驾驶舱.html")


def run_module(name):
    """运行单个模块脚本"""
    print(f"\n{'='*50}\n▶ 运行 {name}\n{'='*50}")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / f"{name}.py")],
        capture_output=True, text=True, encoding="utf-8"
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ {name} 运行失败:\n{result.stderr}")
        return False
    return True


def load_all_json():
    """读取所有模块 JSON，合并成 DATA"""
    data = {}
    for name in MODULES:
        json_path = MID_DIR / f"{name}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data[name] = json.load(f)
        else:
            print(f"⚠️ 缺少 {name}.json，跳过")

    # 已下线的看板内容，注入前剔除（2026-08-27：利润瀑布 / 办公室费用效率 / 超60天空置）
    if "m02_出租率" in data:
        data["m02_出租率"].pop("空置60", None)
        if isinstance(data["m02_出租率"].get("组织对比"), dict):
            data["m02_出租率"]["组织对比"].pop("超60天空置占比", None)
    if "m06_利润" in data:
        data["m06_利润"].pop("利润瀑布", None)
    if "m07_组织" in data:
        data.pop("m07_组织")
    return data


def generate_index_xlsx(data):
    """生成 00_取数说明.xlsx（全链路索引）"""
    import pandas as pd
    rows = []
    for name, module_data in data.items():
        rows.append({
            "模块": name,
            "生成时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "数据块数": len(module_data) if isinstance(module_data, dict) else 1,
            "说明": "见对应 m*.xlsx 核查文件"
        })
    df = pd.DataFrame(rows)
    df.to_excel(MID_DIR / "00_取数说明.xlsx", index=False, engine="openpyxl")
    print(f"  -> 00_取数说明.xlsx")


def inject_html(data):
    """将 DATA 注入 HTML 模板，并内联 ECharts 库（生成自包含单文件）"""
    if not HTML_TEMPLATE.exists():
        print(f"⚠️ 未找到 HTML 模板: {HTML_TEMPLATE}")
        print("   跳过 HTML 生成（数据层已完成）")
        return False

    with open(HTML_TEMPLATE, "r", encoding="utf-8") as f:
        html = f.read()

    # 内联 ECharts 库（echarts.min.js 与模板同目录）
    echarts_path = SCRIPT_DIR / "echarts.min.js"
    if echarts_path.exists():
        with open(echarts_path, "r", encoding="utf-8") as f:
            lib = f.read()
        # 该 echarts.min.js 文件首部自带 <script> 包装，内联前剥离，避免 script 嵌套失衡
        stripped = lib.strip()
        if stripped.startswith("<script"):
            stripped = stripped[stripped.index(">") + 1:].strip()
        html = html.replace('<script src="echarts.min.js"></script>', f"<script>\n{stripped}\n</script>")
        print(f"  -> 内联 ECharts 库 ({len(stripped)//1024} KB)")
    else:
        print("  ⚠️ 未找到 echarts.min.js，图表将无法显示")

    # 内联公司 logo（base64 data URI，替换模板左上角占位符）
    logo_path = SCRIPT_DIR / "logo.png"
    if logo_path.exists() and "__LOGO_B64__" in html:
        import base64
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        html = html.replace("__LOGO_B64__", f"data:image/png;base64,{b64}")
        print(f"  -> 内联公司 logo ({len(b64)//1024} KB)")
    elif "__LOGO_B64__" in html:
        html = html.replace('<div class="logo-img"><img src="__LOGO_B64__" alt="顶鼎房屋"></div>', "")
        print("  ⚠️ 未找到 logo.png，左上角不显示 logo")

    # 备份原文件
    if HTML_OUTPUT.exists():
        backup = HTML_OUTPUT.with_suffix(".bak.html")
        HTML_OUTPUT.replace(backup)

    # 注入 DATA
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    if "const DATA = {};" in html:
        html = html.replace("const DATA = {};", f"const DATA = {data_json};")
    else:
        # 找不到占位符则追加
        html = html.replace("</body>", f"<script>const DATA = {data_json};</script></body>")

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  -> {HTML_OUTPUT.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="看板汇总器")
    parser.add_argument("--only", default=None, help="只重跑指定模块，如 m03_收支")
    parser.add_argument("--no-html", action="store_true", help="不生成HTML")
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 顶鼎运营看板汇总器")
    print("=" * 60)

    # 1. 运行模块
    if args.only:
        if not run_module(args.only):
            sys.exit(1)
    else:
        for name in MODULES:
            if not run_module(name):
                print(f"❌ {name} 失败，终止")
                sys.exit(1)

    # 2. 合并 JSON
    print("\n" + "=" * 60)
    print("📦 合并模块 JSON")
    data = load_all_json()
    print(f"  共 {len(data)} 个模块")

    # 3. 生成取数说明
    generate_index_xlsx(data)

    # 4. 注入 HTML
    if not args.no_html:
        inject_html(data)

    print("\n✅ 汇总完成")


if __name__ == "__main__":
    main()
