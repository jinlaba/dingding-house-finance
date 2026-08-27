-- ============================================================
-- 07_组织.sql  —  fct_办公室费用 / fct_当期收房
-- ============================================================
-- 用途：各组织办公室费用效率（费用÷收房套数）
-- （fct_类型热力 / fct_状态分布 已按用户要求移除，不再呈现）
-- ============================================================

-- 清理已废弃的视图
DROP VIEW IF EXISTS fct_类型热力 CASCADE;
DROP VIEW IF EXISTS fct_状态分布 CASCADE;

-- fct_办公室费用：数据汇总表，大类=办公室费用，2025年起按年累计
-- 实付金额为负数（记账口径），取绝对值输出为正的费用额
CREATE OR REPLACE VIEW fct_办公室费用 AS
SELECT
    LEFT(to_char(实收付日期, 'YYYY'), 4) AS 年份,
    组织,
    COALESCE(ABS(SUM(实付金额)), 0) AS 办公室费用
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
  AND 大类 = '办公室费用'
  AND 组织 IS NOT NULL AND 组织 != ''
GROUP BY LEFT(to_char(实收付日期, 'YYYY'), 4), 组织
ORDER BY 年份, 组织;

-- fct_当期收房：收房统计表按年+组织
-- ⚠️ 收房年份原值带「年」字（如"2026年"），取 LEFT(收房年份,4) 提取纯年份，
--    否则与 fct_办公室费用 的年份 JOIN 不上 → 单房费用被放大数倍
-- ⚠️ 视图列类型变更（旧 年份 varchar → 新 text），需 DROP CASCADE 重建
DROP VIEW IF EXISTS fct_当期收房 CASCADE;
CREATE OR REPLACE VIEW fct_当期收房 AS
SELECT
    LEFT(收房年份, 4) AS 年份,
    组织机构 AS 组织,
    COUNT(*) AS 收房套数
FROM 收房统计表
WHERE 物业地址 IS NOT NULL AND 物业地址 != ''
  AND LEFT(收房年份, 4) >= '2025'
  AND 组织机构 IS NOT NULL AND 组织机构 != ''
GROUP BY LEFT(收房年份, 4), 组织机构
ORDER BY 年份, 组织;
