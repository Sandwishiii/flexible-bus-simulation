"""
距离矩阵预计算
"""
from typing import List, Dict, Optional, Tuple
from core.stop import Stop
from utils.geo import haversine_distance


class DistanceMatrix:
    def __init__(self, stops, vehicle_speed=30.0):
        self.stops = stops
        self.vehicle_speed = vehicle_speed
        self._id_to_idx = {}
        for i, s in enumerate(stops):
            self._id_to_idx[s.stop_id] = i
        n = len(stops)
        self._dist_matrix = [[0.0] * n for _ in range(n)]
        self._time_matrix = [[0.0] * n for _ in range(n)]
        self._polyline_cache = {}
        self._built = False

    def build(self, mode="haversine", api_key=None):
        n = len(self.stops)
        if mode == "haversine":
            self._build_haversine()
        elif mode == "navigation":
            self._build_navigation(api_key)
        else:
            raise ValueError(f"不支持的模式: {mode}")
        self._built = True

    def _build_haversine(self):
        n = len(self.stops)
        speed_ms = self.vehicle_speed / 3.6
        for i in range(n):
            for j in range(i + 1, n):
                dist = haversine_distance(self.stops[i].lng, self.stops[i].lat, self.stops[j].lng, self.stops[j].lat)
                dur = dist / speed_ms if speed_ms > 0 else 0
                self._dist_matrix[i][j] = dist
                self._dist_matrix[j][i] = dist
                self._time_matrix[i][j] = dur
                self._time_matrix[j][i] = dur

    def _build_navigation(self, api_key=None):
        from utils.navigation import AmapDirection
        direction = AmapDirection(api_key)
        n = len(self.stops)
        for i in range(n):
            for j in range(i + 1, n):
                try:
                    result = direction.driving(origin=(self.stops[i].lng, self.stops[i].lat), destination=(self.stops[j].lng, self.stops[j].lat))
                    dist = result["distance"]
                    dur = result["duration"]
                    self._dist_matrix[i][j] = dist
                    self._dist_matrix[j][i] = dist
                    self._time_matrix[i][j] = dur
                    self._time_matrix[j][i] = dur
                    if result.get("polyline"):
                        self._polyline_cache[(i, j)] = result["polyline"]
                        self._polyline_cache[(j, i)] = list(reversed(result["polyline"]))
                except Exception:
                    dist = haversine_distance(self.stops[i].lng, self.stops[i].lat, self.stops[j].lng, self.stops[j].lat)
                    speed_ms = self.vehicle_speed / 3.6
                    dur = dist / speed_ms if speed_ms > 0 else 0
                    self._dist_matrix[i][j] = dist
                    self._dist_matrix[j][i] = dist
                    self._time_matrix[i][j] = dur
                    self._time_matrix[j][i] = dur

    def get_distance(self, stop_id_a, stop_id_b):
        i = self._id_to_idx.get(stop_id_a)
        j = self._id_to_idx.get(stop_id_b)
        if i is None or j is None:
            return 0.0
        return self._dist_matrix[i][j]

    def get_duration(self, stop_id_a, stop_id_b):
        i = self._id_to_idx.get(stop_id_a)
        j = self._id_to_idx.get(stop_id_b)
        if i is None or j is None:
            return 0.0
        return self._time_matrix[i][j]

    def get_polyline(self, stop_id_a, stop_id_b):
        i = self._id_to_idx.get(stop_id_a)
        j = self._id_to_idx.get(stop_id_b)
        if i is None or j is None:
            return []
        return self._polyline_cache.get((i, j), [])

    def find_nearest_stop(self, lng, lat):
        if not self.stops:
            return None
        min_dist = float("inf")
        nearest = None
        for stop in self.stops:
            dist = haversine_distance(stop.lng, stop.lat, lng, lat)
            if dist < min_dist:
                min_dist = dist
                nearest = stop
        return nearest

    @property
    def is_built(self):
        return self._built
