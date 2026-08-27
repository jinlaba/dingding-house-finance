-- ============================================================
-- 06_利润.sql  —  fct_已实现利润 / fct_剩余价值 / fct_租差分布 / fct_类型利润
-- ============================================================
-- 用途：每套房赚不赚钱（已实现+剩余价值=完整利润）
-- ============================================================

-- fct_已实现利润：数据汇总表按组织×大类聚合
-- 托管收入 - 托管支出 + 装修收入 - 装修支出 = 已实现利润
CREATE OR REPLACE VIEW fct_已实现利润 AS
SELECT
    to_char(实收付日期, 'YYYY-MM') AS 月份,
    组织,
    COALESCE(SUM(实收金额) FILTER (WHERE 大类 = '托管收入'), 0)  AS 托管收入,
    COALESCE(SUM(实付金额) FILTER (WHERE 大类 = '托管支出'), 0)  AS 托管支出,
    COALESCE(SUM(实收金额) FILTER (WHERE 大类 = '装修收入'), 0)  AS 装修收入,
    COALESCE(SUM(实付金额) FILTER (WHERE 大类 = '装修支出'), 0)  AS 装修支出,
    COALESCE(SUM(实收金额) FILTER (WHERE 大类 = '托管收入'), 0)
    + COALESCE(SUM(实付金额) FILTER (WHERE 大类 = '托管支出'), 0)
    + COALESCE(SUM(实收金额) FILTER (WHERE 大类 = '装修收入'), 0)
    + COALESCE(SUM(实付金额) FILTER (WHERE 大类 = '装修支出'), 0) AS 已实现利润
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
  AND 组织 IS NOT NULL AND 组织 != ''
  AND 大类 IN ('托管收入','托管支出','装修收入','装修支出')
GROUP BY to_char(实收付日期, 'YYYY-MM'), 组织
ORDER BY 月份, 组织;

-- fct_剩余价值：剩余价值表，取最新快照，按组织汇总
-- 店面名清洗：TRIM 去首尾空格 + 去「高端/中端房源组」后缀，再匹配 dim_店面组织映射
CREATE OR REPLACE VIEW fct_剩余价值 AS
WITH 最新 AS (
    SELECT * FROM 剩余价值
    WHERE 来源文件 = (SELECT MAX(来源文件) FROM 剩余价值)
)
SELECT
    m.组织机构,
    COUNT(*)                         AS 房源数,
    COALESCE(SUM(
        NULLIF(合计剩余利润（元）,'')::numeric
    ), 0)                           AS 剩余利润合计
FROM 最新 s
JOIN dim_店面组织映射 m
    ON TRIM(regexp_replace(s.店面, '\s+(高端|中端)房源组$', '')) = m.店面
WHERE s.店面 IS NOT NULL AND s.店面 != ''
  AND s.合计剩余利润（元） IS NOT NULL AND s.合计剩余利润（元） != ''
GROUP BY m.组织机构
ORDER BY 剩余利润合计 DESC;

-- fct_租差分布：日租金差，取最新快照，按租差区间分桶
CREATE OR REPLACE VIEW fct_租差分布 AS
WITH 最新 AS (
    SELECT * FROM 日租金差
    WHERE 来源文件 = (SELECT MAX(来源文件) FROM 日租金差)
)
SELECT
    CASE
        WHEN NULLIF(租差,'')::numeric < -500 THEN '亏损(<-500)'
        WHEN NULLIF(租差,'')::numeric < 0 THEN '亏损(-500~0)'
        WHEN NULLIF(租差,'')::numeric < 500 THEN '微利(0~500)'
        WHEN NULLIF(租差,'')::numeric < 1000 THEN '正常(500~1000)'
        WHEN NULLIF(租差,'')::numeric < 1500 THEN '优秀(1000~1500)'
        WHEN NULLIF(租差,'')::numeric >= 1500 THEN '明星(≥1500)'
    END AS 租差区间,
    COUNT(*) AS 套数
FROM 最新
WHERE 租差 IS NOT NULL AND 租差 != ''
  AND 租差 ~ '^-?[0-9]+(\.[0-9]+)?$'
GROUP BY CASE
        WHEN NULLIF(租差,'')::numeric < -500 THEN '亏损(<-500)'
        WHEN NULLIF(租差,'')::numeric < 0 THEN '亏损(-500~0)'
        WHEN NULLIF(租差,'')::numeric < 500 THEN '微利(0~500)'
        WHEN NULLIF(租差,'')::numeric < 1000 THEN '正常(500~1000)'
        WHEN NULLIF(租差,'')::numeric < 1500 THEN '优秀(1000~1500)'
        WHEN NULLIF(租差,'')::numeric >= 1500 THEN '明星(≥1500)'
    END
ORDER BY
    MIN(NULLIF(租差,'')::numeric);

-- fct_类型利润：按房源类型汇总利润
-- 数据汇总表有 业务房源类型、金蝶房源类型 两套类型
CREATE OR REPLACE VIEW fct_类型利润 AS
SELECT
    to_char(实收付日期, 'YYYY-MM') AS 月份,
    组织,
    COALESCE(NULLIF(业务房源类型,''), '未分类') AS 房源类型,
    COALESCE(SUM(实收金额), 0) AS 收入,
    COALESCE(SUM(实付金额), 0) AS 支出,
    COALESCE(SUM(实收金额), 0) + COALESCE(SUM(实付金额), 0) AS 净额
FROM 数据汇总表
WHERE 实收付日期 >= '2025-01-01'
  AND 组织 IS NOT NULL AND 组织 != ''
  AND 大类 IN ('托管收入','托管支出','装修收入','装修支出')
GROUP BY to_char(实收付日期, 'YYYY-MM'), 组织, COALESCE(NULLIF(业务房源类型,''), '未分类')
ORDER BY 月份, 组织, 房源类型;

-- fct_类型健康：已按用户要求移除（2026-08-26），不再呈现
DROP VIEW IF EXISTS fct_类型健康 CASCADE;

-- fct_利润瀑布：利润构成瀑布（按 月份×组织）
-- 收入 → 装修支出 → 托管支出 → 办公室费用 → 利润
-- 往来、分红（股东收支）不计入；装修类=装修支出+装修，托管类=托管支出+托管，办公室=办公室费用+办公室
DROP VIEW IF EXISTS fct_利润瀑布 CASCADE;
CREATE OR REPLACE VIEW fct_利润瀑布 AS
SELECT
    月份,
    组织,
    ROUND(收入::numeric, 2) AS 收入,
    ROUND(装修支出::numeric, 2) AS 装修支出,
    ROUND(托管支出::numeric, 2) AS 托管支出,
    ROUND(办公室费用::numeric, 2) AS 办公室费用,
    ROUND((收入 + 装修支出 + 托管支出 + 办公室费用)::numeric, 2) AS 利润
FROM (
    SELECT
        to_char(实收付日期, 'YYYY-MM') AS 月份,
        组织,
        SUM(CASE WHEN 大类 IN ('托管收入','装修收入') THEN 实收金额 ELSE 0 END) AS 收入,
        SUM(CASE WHEN 大类 IN ('装修支出','装修') THEN 实付金额 ELSE 0 END) AS 装修支出,
        SUM(CASE WHEN 大类 IN ('托管支出','托管') THEN 实付金额 ELSE 0 END) AS 托管支出,
        SUM(CASE WHEN 大类 IN ('办公室费用','办公室') THEN 实付金额 ELSE 0 END) AS 办公室费用
    FROM 数据汇总表
    WHERE 实收付日期 >= '2025-01-01'
      AND 组织 IS NOT NULL AND 组织 != ''
      AND 大类 IS NOT NULL AND 大类 != ''
      AND 大类 NOT IN ('往来','股东收支')
    GROUP BY to_char(实收付日期, 'YYYY-MM'), 组织
) t
ORDER BY 月份, 组织;

-- ============================================================
-- 房源收出房价（视图重建，逻辑同 z06：日租金差最新快照 + 标签补全 + 收房价两级补全）
-- 输出：每套房最新收/出房价 + 租差 + 户型/商圈/金蝶类型
-- 补全链：最新快照收房价(>0) → 商圈同户型均价 → 空（房源小区表缺失，小区级补全不可用，跳过）
-- ============================================================
DROP VIEW IF EXISTS 房源收出房价 CASCADE;
CREATE VIEW 房源收出房价 AS
WITH 最新 AS (
    SELECT
        房源编号, 城市, 店面, 物业地址, 业务类型,
        NULLIF(收房价,'')::numeric AS 收房价快照,
        NULLIF(出房价,'')::numeric AS 出房价,
        NULLIF(租差,'')::numeric   AS 租差
    FROM 日租金差
    WHERE 来源文件 = (SELECT MAX(来源文件) FROM 日租金差)
      AND 物业地址 IS NOT NULL AND 物业地址 != ''
),
房源标签 AS (
    -- 全房源按 房产证名称=物业地址 匹配，数据来源日期倒序取最新（同地址多行取最近）
    SELECT DISTINCT ON (房产证名称)
        房产证名称 AS 物业地址, 户型, 商圈名称
    FROM 全房源
    WHERE 房产证名称 IS NOT NULL AND 房产证名称 != ''
    ORDER BY 房产证名称, 数据来源日期 DESC
),
金蝶类型 AS (
    SELECT DISTINCT ON (全房通流水房源)
        全房通流水房源 AS 物业地址, 金蝶房源类型
    FROM 房源类型
    WHERE 全房通流水房源 IS NOT NULL AND 全房通流水房源 != ''
      AND 金蝶房源类型 IS NOT NULL AND 金蝶房源类型 != ''
    ORDER BY 全房通流水房源
),
带标签 AS (
    SELECT d.*, t.户型, t.商圈名称, k.金蝶房源类型
    FROM 最新 d
    LEFT JOIN 房源标签 t ON d.物业地址 = t.物业地址
    LEFT JOIN 金蝶类型 k ON d.物业地址 = k.物业地址
),
商圈均价 AS (
    SELECT 商圈名称, 户型, ROUND(AVG(收房价快照), 2) AS 商圈同户型均价
    FROM 带标签
    WHERE 收房价快照 > 0 AND 商圈名称 IS NOT NULL AND 户型 IS NOT NULL AND 户型 != ''
    GROUP BY 商圈名称, 户型
)
SELECT
    d.房源编号,
    d.城市,
    d.店面,
    d.物业地址,
    d.业务类型,
    d.户型,
    d.商圈名称,
    d.金蝶房源类型,
    d.收房价快照                                        AS 收房价,
    ROUND(b.商圈同户型均价, 2)                           AS 商圈同户型均价,
    COALESCE(NULLIF(d.收房价快照,0), b.商圈同户型均价)   AS 收房价_最终,
    d.出房价,
    d.租差,
    (SELECT MAX(来源文件) FROM 日租金差)                 AS 快照日期
FROM 带标签 d
LEFT JOIN 商圈均价 b ON d.商圈名称 = b.商圈名称 AND d.户型 = b.户型;

-- ============================================================
-- 房源利润预估表（视图重建，逻辑同顶鼎视图逻辑说明.md 第四章）
-- 每套房全周期盈利 = 实际净收支 + 剩余价值 − 运营成本 − 出房提成 − 出租率调整
--   • 实际收支：数据汇总表按物业地址聚合（大类拆分：托管/装修/提成/办公室费用）
--   • 剩余价值：剩余价值表最新快照；⚠️ 报表行被删除（如雨花切换系统）时自动用
--     「租差 × 剩余月数」倒推测算（数据字典口径），剩余价值来源列区分「报表/倒推」
--   • 三项扣减（用户确认版）：运营成本=130元/月×剩余月数；出房提成=性质含高/奢→出房价×70%×剩余年数、
--     含轻托→出房价×80%×剩余年数、其他→0；出租率调整=收房价×8%×剩余年数
-- ============================================================
DROP VIEW IF EXISTS 房源利润预估表 CASCADE;
CREATE VIEW 房源利润预估表 AS
WITH 基准 AS (
    SELECT MAX(实收付日期)::date AS 基准日 FROM 数据汇总表
),
收支 AS (
    SELECT
        物业地址,
        SUM(COALESCE(实收金额,0)) FILTER (WHERE 大类 = '托管收入')                    AS 实际托管收入,
        SUM(COALESCE(实付金额,0)) FILTER (WHERE 大类 = '托管支出')                    AS 实际托管支出,
        SUM(COALESCE(实收金额,0)) FILTER (WHERE 大类 = '装修收入')                    AS 实际装修收入,
        SUM(COALESCE(实付金额,0)) FILTER (WHERE 大类 IN ('装修支出','装修'))          AS 实际装修支出,
        SUM(COALESCE(实付金额,0)) FILTER (WHERE 大类 IN ('租房提成','收房提成'))      AS 实际提成,
        SUM(COALESCE(实付金额,0)) FILTER (WHERE 大类 = '办公室费用')                  AS 实际办公室费用,
        SUM(COALESCE(实收金额,0)) + SUM(COALESCE(实付金额,0))                         AS 实际净收支,
        MAX(实收付日期)                                                               AS 最后流水日期
    FROM 数据汇总表
    WHERE 物业地址 IS NOT NULL AND 物业地址 != ''
      AND 大类 IN ('托管收入','托管支出','装修收入','装修支出','装修','租房提成','收房提成','办公室费用')
    GROUP BY 物业地址
),
最新组织 AS (
    -- 一套房的流水组织可能变化，取最近一笔流水的组织
    SELECT DISTINCT ON (物业地址) 物业地址, 组织
    FROM 数据汇总表
    WHERE 物业地址 IS NOT NULL AND 物业地址 != ''
      AND 组织 IS NOT NULL AND 组织 != ''
    ORDER BY 物业地址, 实收付日期 DESC
),
剩余价值表 AS (
    SELECT DISTINCT ON (物业地址)
        物业地址,
        NULLIF("合计剩余利润（元）",'')::numeric    AS 报表剩余价值,
        房东合同到期时间                             AS 到期时间
    FROM 剩余价值
    WHERE 物业地址 IS NOT NULL AND 物业地址 != ''
      AND 来源文件 = (SELECT MAX(来源文件) FROM 剩余价值)
    ORDER BY 物业地址
),
类型标签 AS (
    SELECT DISTINCT ON (房产证名称) 房产证名称 AS 物业地址, 房源类型
    FROM 全房源
    WHERE 房产证名称 IS NOT NULL AND 房产证名称 != ''
    ORDER BY 房产证名称, 数据来源日期 DESC
),
房源到期 AS (
    -- 全房源兜底：剩余价值表没有的房源，用全房源业主租期结束
    SELECT DISTINCT ON (房产证名称)
        房产证名称 AS 物业地址,
        NULLIF(业主租期结束,'')::date AS 业主租期结束
    FROM 全房源
    WHERE 房产证名称 IS NOT NULL AND 房产证名称 != ''
      AND 业主租期结束 IS NOT NULL AND 业主租期结束 != ''
    ORDER BY 房产证名称, 数据来源日期 DESC
),
提成性质 AS (
    SELECT DISTINCT ON (物业地址) 物业地址, 性质
    FROM 出租部提成表
    WHERE 物业地址 IS NOT NULL AND 物业地址 != ''
    ORDER BY 物业地址, 年月 DESC
),
收出房价 AS (
    SELECT 物业地址, 收房价_最终, 出房价, 租差 FROM 房源收出房价
)
SELECT
    s.物业地址,
    o.组织,
    t.房源类型,
    p.收房价_最终                                            AS 收房价,
    p.出房价,
    c.性质,
    ROUND(s.实际托管收入::numeric, 2)                         AS 实际托管收入,
    ROUND(s.实际托管支出::numeric, 2)                         AS 实际托管支出,
    ROUND(s.实际装修收入::numeric, 2)                         AS 实际装修收入,
    ROUND(s.实际装修支出::numeric, 2)                         AS 实际装修支出,
    ROUND(s.实际提成::numeric, 2)                             AS 实际提成,
    ROUND(s.实际办公室费用::numeric, 2)                       AS 实际办公室费用,
    ROUND(s.实际净收支::numeric, 2)                           AS 实际净收支,
    v.到期时间,
    GREATEST(0, ROUND(
        (DATE_PART('year',  AGE(COALESCE(v.到期时间, h.业主租期结束)::date, (SELECT 基准日 FROM 基准))) * 12
       + DATE_PART('month', AGE(COALESCE(v.到期时间, h.业主租期结束)::date, (SELECT 基准日 FROM 基准))))::numeric, 0)
    )::int                                                   AS 剩余月数,
    v.报表剩余价值,
    CASE
        WHEN v.报表剩余价值 IS NOT NULL THEN '报表'
        WHEN p.租差 IS NOT NULL AND COALESCE(v.到期时间, h.业主租期结束) IS NOT NULL THEN '倒推测算'
        ELSE NULL
    END                                                       AS 剩余价值来源,
    CASE
        WHEN v.报表剩余价值 IS NOT NULL THEN v.报表剩余价值
        -- 报表行缺失（如雨花切换系统被删除）→ 租差 × 剩余月数 倒推
        WHEN p.租差 IS NOT NULL AND COALESCE(v.到期时间, h.业主租期结束) IS NOT NULL THEN
            ROUND(p.租差 * GREATEST(0,
                (DATE_PART('year',  AGE(COALESCE(v.到期时间, h.业主租期结束)::date, (SELECT 基准日 FROM 基准))) * 12
               + DATE_PART('month', AGE(COALESCE(v.到期时间, h.业主租期结束)::date, (SELECT 基准日 FROM 基准))))::numeric
            ), 2)
        ELSE NULL
    END                                                       AS 剩余价值
FROM 收支 s
LEFT JOIN 最新组织 o ON s.物业地址 = o.物业地址
LEFT JOIN 类型标签 t ON s.物业地址 = t.物业地址
LEFT JOIN 剩余价值表 v ON s.物业地址 = v.物业地址
LEFT JOIN 房源到期 h ON s.物业地址 = h.物业地址
LEFT JOIN 提成性质 c ON s.物业地址 = c.物业地址
LEFT JOIN 收出房价 p ON s.物业地址 = p.物业地址;

-- fct_利润预估汇总：房源利润预估表按组织汇总（含三项扣减与最终价值）
DROP VIEW IF EXISTS fct_利润预估汇总 CASCADE;
CREATE VIEW fct_利润预估汇总 AS
WITH 扣减 AS (
    SELECT
        物业地址, 组织, 实际净收支, 剩余价值, 剩余月数, 收房价, 出房价, 性质, 剩余价值来源,
        ROUND(130::numeric * 剩余月数, 2)                                        AS 运营成本,
        CASE
            WHEN 性质 LIKE '%高%' OR 性质 LIKE '%奢%' THEN ROUND(COALESCE(出房价,0) * 0.7 * (剩余月数/12.0), 2)
            WHEN 性质 LIKE '%轻托%' THEN ROUND(COALESCE(出房价,0) * 0.8 * (剩余月数/12.0), 2)
            ELSE 0
        END                                                                      AS 出房提成,
        ROUND(COALESCE(收房价,0) * 0.08 * (剩余月数/12.0), 2)                     AS 出租率调整
    FROM 房源利润预估表
    WHERE 剩余价值 IS NOT NULL
)
SELECT
    组织,
    COUNT(*)                                          AS 房源数,
    COUNT(*) FILTER (WHERE 剩余价值来源='倒推测算')    AS 倒推测算套数,
    ROUND(SUM(实际净收支), 2)                          AS 实际净收支合计,
    ROUND(SUM(剩余价值), 2)                            AS 剩余价值合计,
    ROUND(SUM(运营成本), 2)                            AS 运营成本合计,
    ROUND(SUM(出房提成), 2)                            AS 出房提成合计,
    ROUND(SUM(出租率调整), 2)                          AS 出租率调整合计,
    ROUND(SUM(实际净收支 + 剩余价值 - 运营成本 - 出房提成 - 出租率调整), 2) AS 最终房源价值合计,
    ROUND(AVG(实际净收支 + 剩余价值 - 运营成本 - 出房提成 - 出租率调整), 2)  AS 单房全周期利润
FROM 扣减
GROUP BY 组织
ORDER BY 最终房源价值合计 DESC NULLS LAST;
