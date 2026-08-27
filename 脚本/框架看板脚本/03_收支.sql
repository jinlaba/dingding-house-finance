-- ============================================================
-- 03_收支.sql  —  fct_净收支大类 / fct_装修收入 / fct_维修费
-- ============================================================
-- 用途：月度收支利润、现金流瀑布、装修收入（样本标注）
-- 数据源：数据汇总表（最终合一产物，26列）
-- ============================================================

-- fct_净收支大类：数据汇总表按 组织×月份×大类 聚合
-- 净额 = 收入 + 支出（支出为负）
-- 大类为空 → '未分类'
CREATE OR REPLACE VIEW fct_净收支大类 AS
SELECT
    to_char(实收付日期, 'YYYY-MM')        AS 月份,
    组织,
    COALESCE(NULLIF(大类,''), '未分类')    AS 大类,
    COALESCE(SUM(实收金额), 0)             AS 收入,
    COALESCE(SUM(实付金额), 0)             AS 支出,
    COALESCE(SUM(实收金额), 0) + COALESCE(SUM(实付金额), 0) AS 净额
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
  AND 组织 IS NOT NULL AND 组织 != ''
GROUP BY to_char(实收付日期, 'YYYY-MM'), 组织, COALESCE(NULLIF(大类,''), '未分类')
ORDER BY 月份, 组织, 大类;

-- fct_月度收支汇总：按月+组织汇总所有大类的收入/支出/净额
CREATE OR REPLACE VIEW fct_月度收支汇总 AS
SELECT
    月份,
    组织,
    SUM(收入) AS 收入合计,
    SUM(支出) AS 支出合计,
    SUM(净额) AS 净额合计
FROM fct_净收支大类
GROUP BY 月份, 组织
ORDER BY 月份, 组织;

-- fct_月度净收支：全公司口径，按月×大类（直接从数据汇总表取数）
-- 月度净收支 = 收入 - 支出，按大类归类展示
CREATE OR REPLACE VIEW fct_月度净收支 AS
SELECT
    to_char(实收付日期, 'YYYY-MM') AS 月份,
    COALESCE(NULLIF(大类,''), '未分类') AS 大类,
    COALESCE(SUM(实收金额), 0) AS 收入,
    COALESCE(SUM(实付金额), 0) AS 支出,
    COALESCE(SUM(实收金额), 0) + COALESCE(SUM(实付金额), 0) AS 净额
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
GROUP BY to_char(实收付日期, 'YYYY-MM'), COALESCE(NULLIF(大类,''), '未分类')
ORDER BY 月份, 大类;

-- fct_大类汇总：全公司按大类汇总（用于瀑布图）
CREATE OR REPLACE VIEW fct_大类汇总 AS
SELECT
    月份,
    大类,
    SUM(收入) AS 收入,
    SUM(支出) AS 支出,
    SUM(净额) AS 净额
FROM fct_净收支大类
GROUP BY 月份, 大类
ORDER BY 月份, 大类;

-- fct_装修收入：三源优先级（新模板 > 装修收入-收房部门 > 装修收入-财务报表）
-- 标注样本
CREATE OR REPLACE VIEW fct_装修收入 AS
SELECT
    to_char(d.实收付日期, 'YYYY-MM') AS 月份,
    d.组织,
    COALESCE(SUM(d.实收金额), 0) AS 装修收入,
    '三源优先级：新模板>收房部门>财务报表' AS 来源说明,
    '样本' AS 数据标注
FROM 数据汇总表 d
WHERE d.实收付日期 >= '2025-01-01'
  AND d.大类 = '装修收入'
  AND d.组织 IS NOT NULL AND d.组织 != ''
GROUP BY to_char(d.实收付日期, 'YYYY-MM'), d.组织
ORDER BY 月份, d.组织;

-- fct_维修费：按组织汇总维修支出（大类=装修支出 中的维修部分）
-- 用于「单房维修费」组织对比
CREATE OR REPLACE VIEW fct_维修费 AS
SELECT
    to_char(实收付日期, 'YYYY-MM') AS 月份,
    组织,
    COALESCE(SUM(实付金额), 0) AS 维修支出
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
  AND 大类 = '装修支出'
  AND 费用类型 LIKE '%维修%'
  AND 组织 IS NOT NULL AND 组织 != ''
GROUP BY to_char(实收付日期, 'YYYY-MM'), 组织
ORDER BY 月份, 组织;

-- vw_check_净收支：大类SUM vs 直算净额
CREATE OR REPLACE VIEW vw_check_净收支 AS
SELECT
    a.月份,
    a.组织,
    a.大类,
    a.收入,
    a.支出,
    a.净额,
    a.收入 + a.支出 AS 直算净额,
    a.净额 - (a.收入 + a.支出) AS 差异
FROM fct_净收支大类 a
WHERE a.净额 - (a.收入 + a.支出) != 0;
