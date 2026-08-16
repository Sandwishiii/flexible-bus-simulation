"""
高德路径规划 API 封装
"""
import time
import requests
from typing import Optional, Tuple, List
from config.settings import city_config


class AmapDirectionError(Exception):
    pass


class AmapDirection:
    DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"
    WALKING_URL = "https://restapi.amap.com/v3/direction/walking"

    def __init__(self, api_key=None):
        if api_key:
            self.api_keys = [api_key]
        elif city_config.amap_keys:
            self.api_keys = list(city_config.amap_keys)
        elif city_config.amap_key:
            self.api_keys = [city_config.amap_key]
        else:
            raise ValueError("高德 API Key 未配置")
        self.api_key = self.api_keys[0]
        self._key_index = 0
        self._last_request_time = 0.0
        self._min_interval = 0.05

    def _switch_key(self):
        if len(self.api_keys) <= 1:
            return False
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        self.api_key = self.api_keys[self._key_index]
        return True

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def driving(self, origin, destination, strategy=0):
        self._throttle()
        params = {"key": self.api_key, "origin": f"{origin[0]:.6f},{origin[1]:.6f}", "destination": f"{destination[0]:.6f},{destination[1]:.6f}", "strategy": strategy, "extensions": "base", "output": "JSON"}
        try:
            resp = requests.get(self.DRIVING_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            if self._switch_key():
                params["key"] = self.api_key
                try:
                    resp = requests.get(self.DRIVING_URL, params=params, timeout=10)
                    data = resp.json()
                except Exception:
                    raise AmapDirectionError(f"驾车路径规划请求失败: {e}")
            else:
                raise AmapDirectionError(f"驾车路径规划请求失败: {e}")
        if data.get("status") != "1":
            if self._switch_key():
                params["key"] = self.api_key
                self._throttle()
                try:
                    resp = requests.get(self.DRIVING_URL, params=params, timeout=10)
                    data = resp.json()
                    if data.get("status") == "1":
                        return self._parse_driving_response(data)
                except Exception:
                    pass
            raise AmapDirectionError(f"驾车路径规划失败: {data.get('info', '未知错误')}")
        return self._parse_driving_response(data)

    def _parse_driving_response(self, data):
        result = {"distance": 0.0, "duration": 0.0, "polyline": [], "status": 1}
        paths = data.get("Route", {}).get("paths", [])
        if not paths:
            return result
        path = paths[0]
        result["distance"] = float(path.get("distance", 0))
        result["duration"] = float(path.get("duration", 0))
        polyline_coords = []
        for step in path.get("steps", []):
            polyline_str = step.get("polyline", "")
            for point_str in polyline_str.split(";"):
                point_str = point_str.strip()
                if "," in point_str:
                    parts = point_str.split(",")
                    polyline_coords.append((float(parts[0]), float(parts[1])))
        result["polyline"] = polyline_coords
        return result

    def walking(self, origin, destination):
        self._throttle()
        params = {"key": self.api_key, "origin": f"{origin[0]:.6f},{origin[1]:.6f}", "destination": f"{destination[0]:.6f},{destination[1]:.6f}", "output": "JSON"}
        try:
            resp = requests.get(self.WALKING_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            raise AmapDirectionError(f"步行路径规划请求失败: {e}")
        if data.get("status") != "1":
            raise AmapDirectionError(f"步行路径规划失败: {data.get('info', '未知错误')}")
        return self._parse_walking_response(data)

    def _parse_walking_response(self, data):
        result = {"distance": 0.0, "duration": 0.0, "polyline": [], "status": 1}
        route = data.get("route", {})
        paths = route.get("paths", [])
        if not paths:
            return result
        path = paths[0]
        result["distance"] = float(path.get("distance", 0))
        result["duration"] = float(path.get("duration", 0))
        polyline_coords = []
        for step in path.get("steps", []):
            polyline_str = step.get("polyline", "")
            for point_str in polyline_str.split(";"):
                point_str = point_str.strip()
                if "," in point_str:
                    parts = point_str.split(",")
                    polyline_coords.append((float(parts[0]), float(parts[1])))
        result["polyline"] = polyline_coords
        return result
