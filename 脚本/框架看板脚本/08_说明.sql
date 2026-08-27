-- ============================================================
-- 08_说明.sql  —  fct_血缘 / fct_未分类占比
-- ============================================================
-- 用途：每个数字从哪来、怎么算的、免责声明（从PG数据库产生）
-- ============================================================

-- fct_血缘：从 information_schema 自动生成模块名/指标说明
CREATE OR REPLACE VIEW fct_血缘 AS
SELECT
    table_name  AS 视图名,
    column_name AS 字段名,
    data_type   AS 数据类型,
    '从PG数据库视图 ' || table_name || ' 取数' AS 数据来源
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
      'dim_组织','dim_月份','dim_店面组织映射',
      'fct_在托','fct_收出退','fct_业主退房','fct_收房类型',
      'fct_出租率','fct_空置损失','fct_空置60',
      'fct_净收支大类','fct_月度收支汇总','fct_大类汇总','fct_装修收入','fct_维修费',
      'fct_押金池','fct_押金池汇总','fct_违约损益',
      'fct_利润表','fct_财务指标',
      'fct_已实现利润','fct_剩余价值','fct_租差分布','fct_类型利润',
      '房源收出房价','房源利润预估表','fct_利润预估汇总',
      'fct_办公室费用','fct_当期收房'
  )
ORDER BY table_name, ordinal_position;

-- fct_未分类占比：数据汇总表大类为空的比例
CREATE OR REPLACE VIEW fct_未分类占比 AS
SELECT
    to_char(实收付日期, 'YYYY-MM') AS 月份,
    COUNT(*) AS 总笔数,
    COUNT(*) FILTER (WHERE 大类 IS NULL OR 大类 = '') AS 未分类笔数,
    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE COUNT(*) FILTER (WHERE 大类 IS NULL OR 大类 = '')::float / COUNT(*)
    END AS 未分类占比
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
GROUP BY to_char(实收付日期, 'YYYY-MM')
ORDER BY 月份;
