# 顶鼎运营驾驶舱

自包含 HTML 看板 + 完整生成管道（数据更新后可重跑复现）。

- **在线查看**：<https://jinlaba.github.io/dingding-house-finance/>
- 直达文件：`顶鼎运营驾驶舱.html`（ECharts 与公司 logo 已内联，可离线打开）

## 目录结构

```
├── 顶鼎运营驾驶舱.html      # 运营驾驶舱（最终交付，自包含）
├── index.html               # GitHub Pages 首页跳转
└── 脚本/框架看板脚本/        # 看板生成管道（数据变动后重跑即可更新看板）
    ├── 00~08_*.sql          # PG 视图层（维度/规模/出租率/收支/资金/财务/利润/组织/说明）
    ├── m00~m08_*.py         # 取数模块（视图 → JSON/xlsx）
    ├── z00_建视图.py         # 执行 SQL 建视图（支持 --only 03 单文件重建）
    ├── z10_看板汇总.py       # 汇总各模块 JSON → 注入模板（内联 ECharts + logo）→ 生成看板
    ├── db.py                # 数据库连接（环境变量 DB_USER/DB_PASSWORD/DB_HOST/DB_PORT，无明文密码）
    ├── 顶鼎运营驾驶舱_模板.html
    ├── echarts.min.js
    ├── logo.png             # 公司 logo（生成时 base64 内联）
    └── 中间数据/             # 各模块 JSON + 审核 xlsx（重跑会覆盖）
```

## 数据更新后重跑

```bash
# 1. 导入最新原始表到 PostgreSQL 库「顶鼎」
# 2. 设置连接环境变量
set DB_USER=postgres
set DB_PASSWORD=你的密码
# 3. 重建视图 + 生成看板（输出到 1projects\顶鼎\）
python z00_建视图.py
python z10_看板汇总.py
```

## 说明

- 看板数据快照：2026-08（业主退房为快照倒推口径，历史月偏低，最新月最准）
- 仓库不含数据库连接凭据与业务知识库文档
