-- ============================================================
-- 02_出租率.sql  —  fct_出租率 / fct_空置损失 / fct_空置60
-- ============================================================
-- 用途：出租率趋势、空置损失、超60天空置占比
-- 公式：出租率 = 1 − C ÷ ((B − D − F) × 30 + E)
--   B=总套数 C=空置天数 D=新出房源数量 E=新出分母 F=半年内到期房源套数
-- 组织出租率 = 该组织下所有店面 B/C/D/E/F 分别相加再套公式
-- ============================================================

-- fct_出租率：店面→组织，各因子相加后按公式计算
CREATE OR REPLACE VIEW fct_出租率 AS
WITH 店面因子 AS (
    SELECT
        t.月份,
        m.组织机构,
        t.店面,
        -- 字段转数值（原始表是 varchar）
        COALESCE(NULLIF(t.总套数,'')::numeric, 0)        AS B,
        COALESCE(NULLIF(t.空置天数,'')::numeric, 0)       AS C,
        COALESCE(NULLIF(t.新出房源数量,'')::numeric, 0)   AS D,
        COALESCE(NULLIF(t.新出分母,'')::numeric, 0)       AS E,
        COALESCE(NULLIF(t.半年内到期房源套数,'')::numeric, 0) AS F
    FROM 店面出租率 t
    JOIN dim_店面组织映射 m ON t.店面 = m.店面
    WHERE t.月份 >= '2025-01'
      AND t.店面 IS NOT NULL AND t.店面 != ''
),
组织因子 AS (
    SELECT
        月份,
        组织机构,
        SUM(B) AS SB,
        SUM(C) AS SC,
        SUM(D) AS SD,
        SUM(E) AS SE,
        SUM(F) AS SF
    FROM 店面因子
    GROUP BY 月份, 组织机构
),
公司因子 AS (
    SELECT
        月份,
        '总公司' AS 组织机构,
        SUM(B) AS SB,
        SUM(C) AS SC,
        SUM(D) AS SD,
        SUM(E) AS SE,
        SUM(F) AS SF
    FROM 店面因子
    GROUP BY 月份
)
SELECT
    月份,
    组织机构,
    SB, SC, SD, SE, SF,
    -- 出租率 = 1 − C ÷ ((B − D − F) × 30 + E)
    -- 分母为0时出租率=NULL（避免除零）
    CASE
        WHEN ((SB - SD - SF) * 30 + SE) = 0 THEN NULL
        ELSE 1 - SC::float / ((SB - SD - SF) * 30 + SE)
    END AS 出租率
FROM 组织因子
UNION ALL
SELECT
    月份,
    组织机构,
    SB, SC, SD, SE, SF,
    CASE
        WHEN ((SB - SD - SF) * 30 + SE) = 0 THEN NULL
        ELSE 1 - SC::float / ((SB - SD - SF) * 30 + SE)
    END AS 出租率
FROM 公司因子
ORDER BY 月份, 组织机构;

-- fct_空置损失：租赁概况统计，需先匹配全房源租期
-- 只有「租期结束日期 >= 来源文件日期」的数据才有效（租期未过、仍在公司管理期内的空置才有损失意义）
CREATE OR REPLACE VIEW fct_空置损失 AS
SELECT
    s.来源文件,
    m.组织机构,
    COUNT(*)                        AS 房源数,
    COALESCE(SUM(NULLIF(s.空置损失,'')::numeric), 0) AS 空置损失合计
FROM 租赁概况统计 s
JOIN dim_店面组织映射 m ON s.店面 = m.店面
-- 匹配全房源租期：业主租期结束 >= 来源文件日期 才有效（未过租期）
JOIN 全房源 h ON s.房源编号 = h.房源编码
WHERE s.空置损失 IS NOT NULL AND s.空置损失 != ''
  AND s.店面 IS NOT NULL AND s.店面 != ''
  AND h.业主租期结束 IS NOT NULL AND h.业主租期结束 != ''
  AND NULLIF(h.业主租期结束,'')::date >= NULLIF(s.来源文件,'')::date
GROUP BY s.来源文件, m.组织机构
ORDER BY s.来源文件 DESC, m.组织机构;

-- fct_空置60：超60天空置占比
CREATE OR REPLACE VIEW fct_空置60 AS
WITH 最新快照 AS (
    SELECT * FROM 租赁概况统计
    WHERE 来源文件 = (SELECT MAX(来源文件) FROM 租赁概况统计)
)
SELECT
    m.组织机构,
    COUNT(*) AS 总套数,
    COUNT(*) FILTER (
        WHERE COALESCE(NULLIF(s.空置天数,'')::numeric, 0) > 60
    ) AS 超60套数,
    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE COUNT(*) FILTER (
            WHERE COALESCE(NULLIF(s.空置天数,'')::numeric, 0) > 60
        )::float / COUNT(*)
    END AS 超60占比
FROM 最新快照 s
JOIN dim_店面组织映射 m ON s.店面 = m.店面
WHERE s.店面 IS NOT NULL AND s.店面 != ''
  AND s.空置天数 IS NOT NULL AND s.空置天数 != ''
GROUP BY m.组织机构
ORDER BY 超60占比 DESC;

-- vw_check_出租率：组织加权 vs 总体行（如有差异需排查）
CREATE OR REPLACE VIEW vw_check_出租率 AS
SELECT
    a.月份,
    a.组织机构,
    a.出租率 AS 组织出租率,
    b.出租率 AS 公司出租率,
    a.出租率 - b.出租率 AS 差异
FROM fct_出租率 a
JOIN fct_出租率 b ON a.月份 = b.月份 AND b.组织机构 = '总公司'
WHERE a.组织机构 != '总公司'
  AND a.出租率 IS NOT NULL AND b.出租率 IS NOT NULL
  AND ABS(a.出租率 - b.出租率) > 0.01;
