-- 区域内公交站点筛选
-- 数据源: bus_stations_new
-- 区域表: region_table (name + geom)
-- 输出: name, lng, lat

WITH region AS (
    SELECT geom FROM region_table WHERE name = '双龙新区' LIMIT 1
)
SELECT DISTINCT
    s.stop_name AS name, s.gcj02_lon AS lng, s.gcj02_lat AS lat
FROM bus_stations_new s, region
WHERE
    ST_Within(
        ST_SetSRID(ST_MakePoint(s.gcj02_lon::float8, s.gcj02_lat::float8), 4326),
        region.geom
    )
ORDER BY s.stop_name;
