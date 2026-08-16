"""
OD 数据加载器
支持从 CSV 文件加载高德 OD 数据，并转换为仿真订单
"""
import csv
import math
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ODRecord:
    origin_lng: float
    origin_lat: float
    dest_lng: float
    dest_lat: float
    total_demand: int
    duration: float = 0.0
    distance: float = 0.0
    peak: str = "-"


@dataclass
class OrderRequest:
    origin_lng: float
    origin_lat: float
    dest_lng: float
    dest_lat: float
    request_time: float
    passenger_count: int = 1
    source_od_index: int = -1


class ODLoader:
    def __init__(self):
        self.records: List[ODRecord] = []
        self._raw_rows: List[Dict] = []
        self._format: str = "unknown"

    def load_csv(self, filepath, encoding="utf-8-sig"):
        self.records = []
        self._raw_rows = []
        with open(filepath, "r", encoding=encoding) as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if "o_x" in headers or "total_uv" in headers or "total_trips" in headers:
                self._format = "top200"
            elif "origin_lng" in headers:
                self._format = "generic"
            else:
                raise ValueError(f"无法识别 CSV 格式。列名: {headers}")
            for row in reader:
                self._raw_rows.append(row)
        if self._format == "top200":
            self._parse_top200()
        else:
            self._parse_generic()
        return len(self.records)

    def load_from_string(self, content):
        import io
        self.records = []
        self._raw_rows = []
        reader = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames or []
        if "o_x" in headers or "total_uv" in headers or "total_trips" in headers:
            self._format = "top200"
        elif "origin_lng" in headers:
            self._format = "generic"
        else:
            raise ValueError(f"无法识别 CSV 格式。列名: {headers}")
        for row in reader:
            self._raw_rows.append(row)
        if self._format == "top200":
            self._parse_top200()
        else:
            self._parse_generic()
        return len(self.records)

    def _parse_top200(self):
        for row in self._raw_rows:
            try:
                o_x = float(row.get("o_x", 0))
                o_y = float(row.get("o_y", 0))
                d_x = float(row.get("d_x", 0))
                d_y = float(row.get("d_y", 0))
                total = row.get("total_uv") or row.get("total_trips") or "0"
                demand = int(float(total))
                if demand <= 0 or (o_x == 0 and o_y == 0):
                    continue
                duration = float(row.get("duration", 0) or 0)
                distance = float(row.get("distance", 0) or 0)
                peak = row.get("peak", "-") or "-"
                self.records.append(ODRecord(origin_lng=o_x, origin_lat=o_y, dest_lng=d_x, dest_lat=d_y, total_demand=demand, duration=duration, distance=distance, peak=peak))
            except (ValueError, TypeError):
                continue

    def _parse_generic(self):
        for row in self._raw_rows:
            try:
                self.records.append(ODRecord(origin_lng=float(row["origin_lng"]), origin_lat=float(row["origin_lat"]), dest_lng=float(row["dest_lng"]), dest_lat=float(row["dest_lat"]), total_demand=int(float(row.get("passengers", row.get("total_demand", "1"))))))
            except (ValueError, KeyError, TypeError):
                continue

    def filter_by_region(self, region_polygon):
        from data.region import point_in_polygon
        filtered = []
        for rec in self.records:
            o_in = point_in_polygon(rec.origin_lng, rec.origin_lat, region_polygon)
            d_in = point_in_polygon(rec.dest_lng, rec.dest_lat, region_polygon)
            if o_in and d_in:
                filtered.append(rec)
        self.records = filtered

    def filter_by_demand_range(self, min_demand=0, max_demand=-1):
        if max_demand < 0:
            max_demand = float("inf")
        self.records = [r for r in self.records if min_demand <= r.total_demand <= max_demand]

    def filter_top_n(self, n):
        self.records.sort(key=lambda r: r.total_demand, reverse=True)
        self.records = self.records[:n]

    def expand_orders(self, sim_start=0.0, sim_end=3600.0, time_distribution="uniform", peak_hours=None, peak_weight=3.0, max_orders=-1, seed=42):
        rng = random.Random(seed)
        orders = []
        total_demand = sum(r.total_demand for r in self.records)
        if total_demand == 0:
            return []
        scale = 1.0
        if 0 < max_orders < total_demand:
            scale = max_orders / total_demand
        for idx, rec in enumerate(self.records):
            n = max(1, int(rec.total_demand * scale))
            if time_distribution == "peak_weighted":
                times = self._distribute_peak_weighted(n, sim_start, sim_end, peak_hours or [], peak_weight, rng)
            else:
                times = self._distribute_uniform(n, sim_start, sim_end, rng)
            for t in times:
                orders.append(OrderRequest(origin_lng=rec.origin_lng, origin_lat=rec.origin_lat, dest_lng=rec.dest_lng, dest_lat=rec.dest_lat, request_time=t, passenger_count=1, source_od_index=idx))
        orders.sort(key=lambda o: o.request_time)
        return orders

    def _distribute_uniform(self, n, start, end, rng):
        return [rng.uniform(start, end) for _ in range(n)]

    def _distribute_peak_weighted(self, n, start, end, peak_hours, peak_weight, rng):
        if not peak_hours:
            return self._distribute_uniform(n, start, end, rng)
        duration = end - start
        peak_total = sum(e - s for s, e in peak_hours if s < end and e > start)
        offpeak_total = max(0, duration - peak_total)
        weighted_peak = peak_total * peak_weight
        weighted_total = weighted_peak + offpeak_total
        peak_prob = weighted_peak / weighted_total if weighted_total > 0 else 0
        times = []
        for _ in range(n):
            if rng.random() < peak_prob:
                valid_peaks = [(max(s, start), min(e, end)) for s, e in peak_hours if s < end and e > start]
                if valid_peaks:
                    chosen = rng.choice(valid_peaks)
                    times.append(rng.uniform(chosen[0], chosen[1]))
                else:
                    times.append(rng.uniform(start, end))
            else:
                times.append(rng.uniform(start, end))
        return times

    def get_summary(self):
        if not self.records:
            return {"total_records": 0, "total_demand": 0}
        demands = [r.total_demand for r in self.records]
        return {"total_records": len(self.records), "total_demand": sum(demands), "avg_demand": sum(demands) / len(demands), "max_demand": max(demands), "min_demand": min(demands), "format": self._format}

    def get_records(self):
        return self.records
