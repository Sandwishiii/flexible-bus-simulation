"""
站点数据加载器
"""
import re
import csv
import io
from typing import List, Optional
from core.stop import Stop


class StationLoader:
    def __init__(self):
        self.stops: List[Stop] = []
        self._raw_data: List[dict] = []

    def load_sql_file(self, filepath, encoding="utf-8"):
        with open(filepath, "r", encoding=encoding) as f:
            content = f.read()
        return self.load_sql_string(content)

    def load_sql_string(self, content):
        self.stops = []
        self._raw_data = []
        pattern = re.compile(r"\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*'([^']*)'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,")
        for match in pattern.finditer(content):
            self._raw_data.append({"route_name": match.group(1), "direction": match.group(2), "seq_no": int(match.group(3)), "stop_name": match.group(4), "gcj02_lon": float(match.group(5)), "gcj02_lat": float(match.group(6))})
        self._build_stops()
        return len(self.stops)

    def load_csv(self, filepath, encoding="utf-8-sig"):
        with open(filepath, "r", encoding=encoding) as f:
            content = f.read()
        return self.load_csv_string(content)

    def load_csv_string(self, content):
        self.stops = []
        self._raw_data = []
        reader = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames or []
        name_col = lng_col = lat_col = None
        for h in headers:
            hl = h.lower().strip()
            if hl in ("name", "stop_name", "站点名称", "站名"):
                name_col = h
            elif hl in ("lng", "lon", "gcj02_lon", "经度", "longitude"):
                lng_col = h
            elif hl in ("lat", "gcj02_lat", "纬度", "latitude"):
                lat_col = h
        if not name_col or not lng_col or not lat_col:
            raise ValueError(f"CSV 列名无法识别。实际列名: {headers}")
        for row in reader:
            try:
                self._raw_data.append({"stop_name": row[name_col].strip(), "gcj02_lon": float(row[lng_col]), "gcj02_lat": float(row[lat_col]), "route_name": row.get("route_name", ""), "direction": row.get("direction", ""), "seq_no": int(row.get("seq_no", 0) or 0)})
            except (ValueError, KeyError):
                continue
        self._build_stops()
        return len(self.stops)

    def _build_stops(self):
        seen = set()
        self.stops = []
        for data in self._raw_data:
            name = data["stop_name"]
            lon = data["gcj02_lon"]
            lat = data["gcj02_lat"]
            key = (name, round(lon, 6), round(lat, 6))
            if key in seen:
                continue
            seen.add(key)
            stop_id = f"S{len(self.stops) + 1:03d}"
            self.stops.append(Stop(stop_id=stop_id, name=name, lng=lon, lat=lat))

    def get_stops(self):
        return self.stops

    def get_summary(self):
        if not self.stops:
            return {"total_stops": 0}
        routes = set(d.get("route_name", "") for d in self._raw_data if d.get("route_name"))
        return {"total_stops": len(self.stops), "total_routes": len(routes), "routes": sorted(routes)}
