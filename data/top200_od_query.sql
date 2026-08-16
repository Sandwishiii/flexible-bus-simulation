-- 区域内 Top200 OD 对统计
-- 数据源: amap_guiyang_shuanglong (高德OD数据)
-- 区域表: region_table (name + geom)
-- 输出: o_x, o_y, d_x, d_y, total_uv

WITH region AS (
    SELECT geom FROM region_table WHERE name = '你的区域名称' LIMIT 1
)
SELECT
    o_x::float8, o_y::float8, d_x::float8, d_y::float8,
    SUM(uv::bigint) AS total_uv
FROM amap_guiyang_shuanglong, region
WHERE
    o_x ~ '^\d+\.\d+$' AND o_y ~ '^\d+\.\d+$'
    AND d_x ~ '^\d+\.\d+$' AND d_y ~ '^\d+\.\d+$'
    AND uv ~ '^\d+$'
    AND ST_Within(ST_SetSRID(ST_MakePoint(o_x::float8, o_y::float8), 4326), region.geom)
    AND ST_Within(ST_SetSRID(ST_MakePoint(d_x::float8, d_y::float8), 4326), region.geom)
GROUP BY o_x, o_y, d_x, d_y
ORDER BY total_uv DESC
LIMIT 200;
