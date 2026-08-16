"""
区域 WKT 处理模块
"""
import re
from typing import List, Tuple


def parse_wkt_polygon(wkt):
    wkt = wkt.strip()
    match = re.search(r'(?:MULTI)?POLYGON\s*\(\s*\(\s*(.+?)\s*\)', wkt, re.IGNORECASE)
    if not match:
        match = re.search(r'\(\s*\((.+?)\)\s*\)', wkt)
    if not match:
        raise ValueError(f"无法解析 WKT: {wkt[:100]}...")
    coord_str = match.group(1)
    points = []
    for pair in coord_str.split(","):
        pair = pair.strip()
        parts = pair.split()
        if len(parts) >= 2:
            points.append((float(parts[0]), float(parts[1])))
    if len(points) < 3:
        raise ValueError(f"多边形至少需要 3 个顶点")
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    return points


def point_in_polygon(lng, lat, polygon):
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def points_in_polygon(points, polygon):
    return [point_in_polygon(p[0], p[1], polygon) for p in points]


def polygon_bbox(polygon):
    lngs = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    return min(lngs), min(lats), max(lngs), max(lats)
