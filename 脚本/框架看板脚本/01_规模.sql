-- ============================================================
-- 01_规模.sql  —  fct_在托 / fct_收出退 / fct_收房类型
-- ============================================================
-- 用途：在管规模趋势、收出退房吞吐、收房类型结构
-- ============================================================

-- 旧版 fct_收出退 月份列类型为 varchar，新版为 text，无法 OR REPLACE；先删依赖视图再重建
DROP VIEW IF EXISTS vw_check_在托;
DROP VIEW IF EXISTS fct_收出退;

-- fct_在托：在托房源按月+组织汇总套数
CREATE OR REPLACE VIEW fct_在托 AS
SELECT
    t.年月                                                  AS 月份,
    m.组织机构,
    COUNT(t.物业地址)                                       AS 在托套数
FROM 在托房源 t
JOIN dim_店面组织映射 m ON t.店面 = m.店面
WHERE t.年月 >= '2025-01'
  AND t.物业地址 IS NOT NULL AND t.物业地址 != ''
GROUP BY t.年月, m.组织机构
ORDER BY t.年月, m.组织机构;

-- fct_收出退：收房/出房/租客退房/退房违约 按月+组织
-- 口径说明（用户确认版）：
--   收房     = 收房统计表（业主口径：从业主收进房源）
--   出房     = 新租房源（租客口径：出租给租客）
--   租客退房 = 租客已退房登记日期（租客口径：租客退租）
--   业主退房 = fct_业主退房（业主口径：按业主租期到期倒推，仅最新快照，不按月回溯）
-- 收房统计表 收房年份='2025年'、收房月份='1'/'10月' 混合格式 → 组合成 YYYY-MM
-- 新租房源 月份='202501'（YYYYMM）→ 转 YYYY-MM
CREATE OR REPLACE VIEW fct_收出退 AS
SELECT
    月份,
    组织机构,
    SUM(收房) AS 收房,
    SUM(出房) AS 出房,
    SUM(租客退房) AS 租客退房,
    SUM(退房违约) AS 退房违约
FROM (
    -- 收房
    SELECT
        LEFT(收房年份,4) || '-' || LPAD(regexp_replace(收房月份,'[^0-9]','','g'),2,'0') AS 月份,
        组织机构,
        COUNT(*) AS 收房,
        0 AS 出房, 0 AS 租客退房, 0 AS 退房违约
    FROM 收房统计表
    WHERE 收房年份 IS NOT NULL AND 收房年份 != ''
      AND 收房月份 IS NOT NULL AND 收房月份 != ''
      AND 收房月份 ~ '[0-9]'
      AND 物业地址 IS NOT NULL AND 物业地址 != ''
      AND LEFT(收房年份,4) || '-' || LPAD(regexp_replace(收房月份,'[^0-9]','','g'),2,'0') >= '2025-01'
    GROUP BY LEFT(收房年份,4) || '-' || LPAD(regexp_replace(收房月份,'[^0-9]','','g'),2,'0'), 组织机构

    UNION ALL

    -- 出房：新租房源（2026-04/05/06 物业地址为空，改用店面关联，不依赖物业地址）
    SELECT
        LEFT(n.月份,4) || '-' || SUBSTR(n.月份,5,2) AS 月份,
        m.组织机构,
        0 AS 收房,
        COUNT(*) AS 出房,
        0 AS 租客退房, 0 AS 退房违约
    FROM 新租房源 n
    JOIN dim_店面组织映射 m ON n.店面 = m.店面
    WHERE n.月份 IS NOT NULL AND n.月份 != ''
      AND n.月份 ~ '^[0-9]{6}$'
      AND LEFT(n.月份,4) || '-' || SUBSTR(n.月份,5,2) >= '2025-01'
    GROUP BY LEFT(n.月份,4) || '-' || SUBSTR(n.月份,5,2), m.组织机构

    UNION ALL

    -- 租客退房（含违约标记）
    SELECT
        to_char(退房时间, 'YYYY-MM') AS 月份,
        m.组织机构,
        0 AS 收房, 0 AS 出房,
        COUNT(*) AS 租客退房,
        COUNT(*) FILTER (WHERE 退款状态 IN ('不退款','未退')) AS 退房违约
    FROM 租客已退房登记日期 r
    JOIN dim_店面组织映射 m ON r.店面 = m.店面
    WHERE to_char(退房时间, 'YYYY-MM') >= '2025-01'
      AND r.物业地址 IS NOT NULL AND r.物业地址 != ''
    GROUP BY to_char(退房时间, 'YYYY-MM'), m.组织机构
) combined
GROUP BY 月份, 组织机构
ORDER BY 月份, 组织机构;

-- fct_业主退房：业主口径退房（房源退出在管），按业主租期到期倒推
-- 数据源：全房源最新快照（数据来源日期取最大值）
-- 口径：业主租期结束落在某月 = 该月业主退房（到期房源应归还业主）
-- 月份序列：>= 2025-01 且 <= 快照日期（排除未来到期）
-- ⚠️ 快照倒推局限：已实际退出的房源不在快照中，历史月份数字偏低，最新月最准
-- ⚠️ 视图列结构变更（旧版无月份列、有快照月份/快照总套数列），需 DROP CASCADE 重建
DROP VIEW IF EXISTS fct_业主退房 CASCADE;
CREATE OR REPLACE VIEW fct_业主退房 AS
SELECT
    m.组织机构,
    to_char(NULLIF(h.业主租期结束,'')::date, 'YYYY-MM') AS 月份,
    COUNT(*) AS 业主退房套数
FROM 全房源 h
JOIN dim_店面组织映射 m ON h."店面(流水)" = m.店面
WHERE h.数据来源日期 = (SELECT MAX(数据来源日期) FROM 全房源)
  AND NULLIF(h.业主租期结束,'')::date IS NOT NULL
  AND NULLIF(h.业主租期结束,'')::date <= (SELECT MAX(数据来源日期) FROM 全房源)::date
  AND to_char(NULLIF(h.业主租期结束,'')::date, 'YYYY-MM') >= '2025-01'
  AND h."店面(流水)" IS NOT NULL AND h."店面(流水)" != ''
GROUP BY m.组织机构, to_char(NULLIF(h.业主租期结束,'')::date, 'YYYY-MM')
ORDER BY 月份, m.组织机构;

-- fct_收房类型：收房统计表按统计类型
CREATE OR REPLACE VIEW fct_收房类型 AS
SELECT
    统计类型,
    COUNT(*) AS 套数
FROM 收房统计表
WHERE 物业地址 IS NOT NULL AND 物业地址 != ''
  AND 统计类型 IS NOT NULL AND 统计类型 != ''
GROUP BY 统计类型
ORDER BY 套数 DESC;

-- vw_check_在托：存量 vs 流量交叉验证
-- 上期末在托 + 收房 - 退房 = 本期末在托（差异>0 表示有未捕获的变动）
CREATE OR REPLACE VIEW vw_check_在托 AS
WITH prev AS (
    SELECT 组织机构, 在托套数 AS 上期末
    FROM fct_在托
    WHERE 月份 = (SELECT MAX(月份) FROM fct_在托 WHERE 月份 < (SELECT MAX(月份) FROM fct_在托))
),
curr AS (
    SELECT 组织机构, 在托套数 AS 本期末
    FROM fct_在托
    WHERE 月份 = (SELECT MAX(月份) FROM fct_在托)
),
flow AS (
    SELECT 组织机构, COALESCE(SUM(收房),0) AS 收房, COALESCE(SUM(租客退房),0) AS 租客退房
    FROM fct_收出退
    WHERE 月份 = (SELECT MAX(月份) FROM fct_在托)
    GROUP BY 组织机构
)
SELECT
    COALESCE(p.组织机构, c.组织机构, f.组织机构) AS 组织机构,
    COALESCE(p.上期末, 0)      AS 上期末在托,
    COALESCE(f.收房, 0)        AS 本期收房,
    COALESCE(f.租客退房, 0)     AS 本期租客退房,
    COALESCE(c.本期末, 0)      AS 本期末在托,
    COALESCE(p.上期末, 0) + COALESCE(f.收房, 0) - COALESCE(f.租客退房, 0) AS 计算值,
    COALESCE(c.本期末, 0) - (COALESCE(p.上期末, 0) + COALESCE(f.收房, 0) - COALESCE(f.租客退房, 0)) AS 差异
FROM prev p
FULL OUTER JOIN curr c ON p.组织机构 = c.组织机构
FULL OUTER JOIN flow f ON COALESCE(p.组织机构, c.组织机构) = f.组织机构
WHERE COALESCE(c.本期末, 0) - (COALESCE(p.上期末, 0) + COALESCE(f.收房, 0) - COALESCE(f.租客退房, 0)) != 0;
