-- ============================================================
-- 05_财务.sql  —  fct_利润表 / fct_资产负债表 / fct_现金流量表 / fct_财务指标
-- ============================================================
-- 用途：法定报表口径下公司盈利水平、资产负债、现金流
-- 口径：表头行有各组织，「合并数」列=总公司；选具体组织=合并数+该组织个别数
-- 利润表/现金流量表列名带「(本年累计数)」，资产负债表带「(期末数)」，用 DO 块动态生成视图
-- 三表均有多个期间（来源文件），财务指标取最新期间
-- ============================================================

-- fct_利润表：将列式报表转为行式（期间 × 报表项目 × 列名 × 金额）
-- 动态读取 information_schema 中所有「个别数」列，自动生成 UNION ALL
DO $$
DECLARE
    col RECORD;
    parts TEXT[] := '{}';
    org_name TEXT;
BEGIN
    DROP VIEW IF EXISTS fct_利润表 CASCADE;
    FOR col IN
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '利润'
          AND column_name LIKE '%个别数(本年累计数)%'
        ORDER BY ordinal_position
    LOOP
        org_name := replace(col.column_name, '个别数(本年累计数)', '');
        parts := parts || format(
            'SELECT 来源文件, 报表项目, %L AS 列名, NULLIF(%I, %L)::numeric AS 金额 FROM 利润 WHERE 报表项目 IS NOT NULL AND 报表项目 != %L',
            org_name, col.column_name, '', ''
        );
    END LOOP;
    parts := array_prepend(
        'SELECT 来源文件, 报表项目, ''合并数'' AS 列名, NULLIF("合并数(本年累计数)", '''')::numeric AS 金额 FROM 利润 WHERE 报表项目 IS NOT NULL AND 报表项目 != ''''',
        parts
    );
    EXECUTE 'CREATE OR REPLACE VIEW fct_利润表 AS ' || array_to_string(parts, ' UNION ALL ');
END $$;

-- fct_资产负债表：将列式报表转为行式（期间 × 报表项目 × 列名 × 金额）
-- 资产负债表列名带「(期末数)」后缀
DO $$
DECLARE
    col RECORD;
    parts TEXT[] := '{}';
    org_name TEXT;
BEGIN
    DROP VIEW IF EXISTS fct_资产负债表 CASCADE;
    FOR col IN
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '资产'
          AND column_name LIKE '%个别数(期末数)%'
        ORDER BY ordinal_position
    LOOP
        org_name := replace(col.column_name, '个别数(期末数)', '');
        parts := parts || format(
            'SELECT 来源文件, 报表项目, %L AS 列名, NULLIF(%I, %L)::numeric AS 金额 FROM 资产 WHERE 报表项目 IS NOT NULL AND 报表项目 != %L',
            org_name, col.column_name, '', ''
        );
    END LOOP;
    parts := array_prepend(
        'SELECT 来源文件, 报表项目, ''合并数'' AS 列名, NULLIF("合并数(期末数)", '''')::numeric AS 金额 FROM 资产 WHERE 报表项目 IS NOT NULL AND 报表项目 != ''''',
        parts
    );
    EXECUTE 'CREATE OR REPLACE VIEW fct_资产负债表 AS ' || array_to_string(parts, ' UNION ALL ');
END $$;

-- fct_现金流量表：将列式报表转为行式（期间 × 报表项目 × 列名 × 金额）
-- 现金流量表列名带「(本年累计数)」后缀
DO $$
DECLARE
    col RECORD;
    parts TEXT[] := '{}';
    org_name TEXT;
BEGIN
    DROP VIEW IF EXISTS fct_现金流量表 CASCADE;
    FOR col IN
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '现金流量'
          AND column_name LIKE '%个别数(本年累计数)%'
        ORDER BY ordinal_position
    LOOP
        org_name := replace(col.column_name, '个别数(本年累计数)', '');
        parts := parts || format(
            'SELECT 来源文件, 报表项目, %L AS 列名, NULLIF(%I, %L)::numeric AS 金额 FROM 现金流量 WHERE 报表项目 IS NOT NULL AND 报表项目 != %L',
            org_name, col.column_name, '', ''
        );
    END LOOP;
    parts := array_prepend(
        'SELECT 来源文件, 报表项目, ''合并数'' AS 列名, NULLIF("合并数(本年累计数)", '''')::numeric AS 金额 FROM 现金流量 WHERE 报表项目 IS NOT NULL AND 报表项目 != ''''',
        parts
    );
    EXECUTE 'CREATE OR REPLACE VIEW fct_现金流量表 AS ' || array_to_string(parts, ' UNION ALL ');
END $$;

-- fct_财务指标：从利润表取关键行计算指标（合并数口径，最新期间）
-- 毛利率 = (营业收入 - 营业成本) / 营业收入
-- 净利率 = 净利润 / 营业收入
-- 营业利润率 = 营业利润 / 营业收入
CREATE OR REPLACE VIEW fct_财务指标 AS
WITH pivot_data AS (
    SELECT
        报表项目,
        金额 AS 合并数
    FROM fct_利润表
    WHERE 列名 = '合并数'
      AND 来源文件 = (SELECT MAX(来源文件) FROM fct_利润表)
),
revenue AS (SELECT SUM(合并数) AS 营业收入 FROM pivot_data WHERE 报表项目 LIKE '%营业收入%'),
cost AS (SELECT SUM(合并数) AS 营业成本 FROM pivot_data WHERE 报表项目 LIKE '%营业成本%'),
profit AS (SELECT SUM(合并数) AS 营业利润 FROM pivot_data WHERE 报表项目 LIKE '%营业利润%'),
net AS (SELECT SUM(合并数) AS 净利润 FROM pivot_data WHERE 报表项目 LIKE '%净利润%')
SELECT
    '毛利率' AS 指标,
    '(营业收入-营业成本)/营业收入' AS 公式,
    CASE WHEN (SELECT 营业收入 FROM revenue) = 0 OR (SELECT 营业收入 FROM revenue) IS NULL THEN NULL
         ELSE ((SELECT 营业收入 FROM revenue) - COALESCE((SELECT 营业成本 FROM cost),0)) / (SELECT 营业收入 FROM revenue)
    END AS 值
UNION ALL
SELECT
    '净利率' AS 指标,
    '净利润/营业收入' AS 公式,
    CASE WHEN (SELECT 营业收入 FROM revenue) = 0 OR (SELECT 营业收入 FROM revenue) IS NULL THEN NULL
         ELSE COALESCE((SELECT 净利润 FROM net),0) / (SELECT 营业收入 FROM revenue)
    END AS 值
UNION ALL
SELECT
    '营业利润率' AS 指标,
    '营业利润/营业收入' AS 公式,
    CASE WHEN (SELECT 营业收入 FROM revenue) = 0 OR (SELECT 营业收入 FROM revenue) IS NULL THEN NULL
         ELSE COALESCE((SELECT 营业利润 FROM profit),0) / (SELECT 营业收入 FROM revenue)
    END AS 值;
