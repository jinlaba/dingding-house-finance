-- ============================================================
-- 04_资金.sql  —  fct_押金池 / fct_违约损益
-- ============================================================
-- 用途：押金池规模、违约损益
-- 数据源：科目余额表（部门列为空=汇总数据）
-- ============================================================

-- fct_押金池：科目余额表，按 账簿(组织)×月份×科目大类 聚合
-- 汇总行(核算维度-部门为空)优先；无汇总行时用店面行之和
-- （2241.01租客押金/1221.01业主押金 只有店面行，1002现金 仅2026-03有汇总行）
-- 科目大类：租客押金=2241.01贷方，业主押金=1221.01借方，现金=1002借方
-- 期次=来源文件前7位（YYYY-MM）；账簿去「主账簿」后缀 → 组织
DROP VIEW IF EXISTS fct_押金池 CASCADE;
CREATE OR REPLACE VIEW fct_押金池 AS
WITH 明细 AS (
    SELECT
        LEFT(来源文件, 7) AS 月份,
        CASE
            WHEN "账簿-账簿" LIKE '%主账簿' THEN TRIM(TRAILING '主账簿' FROM "账簿-账簿")
            ELSE "账簿-账簿"
        END AS 账簿,
        CASE
            WHEN "科目编码-科目编码" LIKE '2241.01%' THEN '租客押金'
            WHEN "科目编码-科目编码" LIKE '1221.01%' THEN '业主押金'
            WHEN "科目编码-科目编码" LIKE '1002%' THEN '现金'
        END AS 科目大类,
        "期末余额-借方金额" AS 借方,
        "期末余额-贷方金额" AS 贷方,
        CASE WHEN "核算维度-部门" IS NULL OR "核算维度-部门" = '' THEN 1 ELSE 0 END AS 是否汇总
    FROM 科目余额表
    WHERE 来源文件 IS NOT NULL AND 来源文件 != ''
      AND (
          "科目编码-科目编码" LIKE '2241.01%'   -- 租客押金
          OR "科目编码-科目编码" LIKE '1221.01%' -- 业主押金
          OR "科目编码-科目编码" LIKE '1002%'    -- 现金/银行存款
      )
),
聚合 AS (
    SELECT
        月份, 账簿, 科目大类,
        SUM(借方) FILTER (WHERE 是否汇总 = 1) AS 汇总借方,
        SUM(贷方) FILTER (WHERE 是否汇总 = 1) AS 汇总贷方,
        SUM(借方) FILTER (WHERE 是否汇总 = 0) AS 明细借方,
        SUM(贷方) FILTER (WHERE 是否汇总 = 0) AS 明细贷方
    FROM 明细
    GROUP BY 月份, 账簿, 科目大类
)
SELECT
    月份, 账簿, 科目大类,
    COALESCE(汇总借方, 明细借方) AS "期末余额-借方金额",
    COALESCE(汇总贷方, 明细贷方) AS "期末余额-贷方金额"
FROM 聚合
ORDER BY 月份, 账簿, 科目大类;

-- fct_押金池汇总：按月份汇总押金池三大科目
CREATE OR REPLACE VIEW fct_押金池汇总 AS
SELECT
    月份,
    SUM("期末余额-贷方金额") FILTER (WHERE 科目大类 = '租客押金') AS 租客押金,
    SUM("期末余额-借方金额") FILTER (WHERE 科目大类 = '业主押金') AS 业主押金,
    SUM("期末余额-借方金额") FILTER (WHERE 科目大类 = '现金')    AS 现金
FROM fct_押金池
GROUP BY 月份
ORDER BY 月份;

-- fct_违约损益：租客已退房登记日期，违约退房 + 不退款/未退
-- 月份 = 退房时间所在月（按月度序列统计）
-- 组织经店面映射；退房套数=该月该组织的全部退房，违约套数=其中不退款/未退部分
-- 违约退房率 = 违约套数/退房套数
-- 注：三个来源文件（2024-12/2026-07/2026-12）数据互不重叠（已核验），直接合并按退房时间统计；
--     未来退房时间（计划退房）按 CURRENT_DATE 截断
DROP VIEW IF EXISTS fct_违约损益 CASCADE;
CREATE OR REPLACE VIEW fct_违约损益 AS
SELECT
    to_char(r.退房时间, 'YYYY-MM') AS 月份,
    m.组织机构,
    COUNT(*)                     AS 退房套数,
    COUNT(*) FILTER (WHERE r.退款状态 IN ('不退款','未退')) AS 违约套数,
    COALESCE(SUM(NULLIF(违约盈利,'')::numeric) FILTER (WHERE r.退款状态 IN ('不退款','未退')), 0) AS 违约损益合计
FROM 租客已退房登记日期 r
JOIN dim_店面组织映射 m ON r.店面 = m.店面
WHERE r.退房时间 IS NOT NULL
  AND r.退房时间 <= CURRENT_DATE
  AND r.物业地址 IS NOT NULL AND r.物业地址 != ''
GROUP BY to_char(r.退房时间, 'YYYY-MM'), m.组织机构
ORDER BY 月份, m.组织机构;
