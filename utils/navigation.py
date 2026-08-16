"""
高德路径规划 API 封装
支持驾车/步行路径规划，返回距离、时间、轨迹坐标
集成 NavCache 本地文件缓存，避免重复调用 API
"""
import time
import random
import requests
from typing import Optional, Tuple, List
from config.settings import city_config
from utils.nav_cache import get_nav_cache


class AmapDirectionError(Exception):
    """高德路径规划 API 异常"""
    pass


class AmapDirection:
    """
    高德路径规划 API 封装

    支持多 Key 池，自动故障切换

    用法:
        direction = AmapDirection()
        result = direction.driving(origin=(106.76, 26.51), destination=(106.78, 26.55))
        print(result['distance'], result['duration'])
    """

    DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"
    WALKING_URL = "https://restapi.amap.com/v3/direction/walking"

    def __init__(self, api_key: Optional[str] = None, use_cache: bool = True):
        # 缓存
        self._cache = get_nav_cache() if use_cache else None

        # 支持多 Key 池
        if api_key:
            self.api_keys = [api_key]
        elif city_config.amap_keys:
            self.api_keys = list(city_config.amap_keys)
        elif city_config.amap_key:
            self.api_keys = [city_config.amap_key]
        else:
            raise ValueError("高德 API Key 未配置，请在 settings.py 中设置 amap_keys")

        self.api_key = self.api_keys[0]  # 当前使用的 Key
        self._key_index = 0

        # 限流：随机 0.3~2s 间隔，避免触发高德频率限制
        self._last_request_time = 0.0
        self._min_interval = 0.3    # 最小间隔
        self._max_interval = 2.0    # 最大间隔
        self._consecutive_errors = 0  # 连续错误计数（用于退避）

    def _switch_key(self) -> bool:
        """切换到下一个 Key，返回是否成功切换"""
        if len(self.api_keys) <= 1:
            return False
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        self.api_key = self.api_keys[self._key_index]
        return True

    def _throttle(self):
        """随机间隔限流 + 连续错误退避"""
        elapsed = time.time() - self._last_request_time
        # 随机基础间隔
        base_delay = random.uniform(self._min_interval, self._max_interval)
        # 连续错误时指数退避：1s, 2s, 4s, 8s...
        if self._consecutive_errors > 0:
            backoff = min(2 ** self._consecutive_errors, 30)
            base_delay = max(base_delay, backoff)
        if elapsed < base_delay:
            time.sleep(base_delay - elapsed)
        self._last_request_time = time.time()

    def _record_success(self):
        """记录成功请求"""
        self._consecutive_errors = 0

    def _record_error(self):
        """记录失败请求，增加退避"""
        self._consecutive_errors += 1

    def driving(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        strategy: int = 0,
    ) -> dict:
        """
        驾车路径规划（支持多 Key 自动故障切换）

        Args:
            origin: (经度, 纬度)
            destination: (经度, 纬度)
            strategy: 导航策略 (0=速度优先)

        Returns:
            {
                'distance': float,   # 行驶距离（米）
                'duration': float,   # 预计时间（秒）
                'polyline': [(lng, lat), ...],  # 轨迹坐标
                'status': int,       # 1=成功
            }
        """
        # ---- 查缓存（缓存命中时不限流，直接返回）----
        if self._cache:
            cached = self._cache.get(origin, destination)
            if cached:
                return cached

        # 缓存未命中，才需要限流并调 API
        self._throttle()

        params = {
            "key": self.api_key,
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{destination[0]:.6f},{destination[1]:.6f}",
            "strategy": strategy,
            "extensions": "all",
            "output": "JSON",
        }

        try:
            resp = requests.get(self.DRIVING_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            self._record_error()
            # 网络错误，尝试切换 Key
            if self._switch_key():
                params["key"] = self.api_key
                self._throttle()
                try:
                    resp = requests.get(self.DRIVING_URL, params=params, timeout=10)
                    data = resp.json()
                except Exception:
                    raise AmapDirectionError(f"驾车路径规划请求失败: {e}")
            else:
                raise AmapDirectionError(f"驾车路径规划请求失败: {e}")

        if data.get("status") != "1":
            self._record_error()
            # API 返回错误，尝试切换 Key
            if self._switch_key():
                params["key"] = self.api_key
                self._throttle()
                try:
                    resp = requests.get(self.DRIVING_URL, params=params, timeout=10)
                    data = resp.json()
                    if data.get("status") == "1":
                        self._record_success()
                        result = self._parse_driving_response(data)
                        # ---- 写缓存 ----
                        if self._cache:
                            self._cache.set(origin, destination, result)
                            self._cache.api_calls += 1
                        return result
                except Exception:
                    pass
            raise AmapDirectionError(
                f"驾车路径规划失败: {data.get('info', '未知错误')} "
                f"(infocode={data.get('infocode', 'N/A')})"
            )

        self._record_success()
        result = self._parse_driving_response(data)
        # ---- 写缓存 ----
        if self._cache:
            self._cache.set(origin, destination, result)
            self._cache.api_calls += 1
        return result

    def _parse_driving_response(self, data: dict) -> dict:
        """解析驾车路径规划响应"""
        result = {
            "distance": 0.0,
            "duration": 0.0,
            "polyline": [],
            "status": 1,
        }

        paths = data.get("route", {}).get("paths", [])
        if not paths:
            return result

        # 取第一条路径
        path = paths[0]
        result["distance"] = float(path.get("distance", 0))
        result["duration"] = float(path.get("duration", 0))

        # 解析轨迹坐标
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

    def walking(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
    ) -> dict:
        """
        步行路径规划

        Args:
            origin: (经度, 纬度)
            destination: (经度, 纬度)

        Returns:
            {
                'distance': float,   # 步行距离（米）
                'duration': float,   # 预计时间（秒）
                'polyline': [(lng, lat), ...],
                'status': int,
            }
        """
        self._throttle()

        params = {
            "key": self.api_key,
            "origin": f"{origin[0]:.6f},{origin[1]:.6f}",
            "destination": f"{destination[0]:.6f},{destination[1]:.6f}",
            "output": "JSON",
        }

        try:
            resp = requests.get(self.WALKING_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            raise AmapDirectionError(f"步行路径规划请求失败: {e}")

        if data.get("status") != "1":
            raise AmapDirectionError(
                f"步行路径规划失败: {data.get('info', '未知错误')}"
            )

        return self._parse_walking_response(data)

    def _parse_walking_response(self, data: dict) -> dict:
        """解析步行路径规划响应"""
        result = {
            "distance": 0.0,
            "duration": 0.0,
            "polyline": [],
            "status": 1,
        }

        route = data.get("route", {})
        paths = route.get("paths", [])
        if not paths:
            return result

        path = paths[0]
        result["distance"] = float(path.get("distance", 0))
        result["duration"] = float(path.get("duration", 0))

        # 解析轨迹
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


def batch_driving_directions(
    pairs: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    api_key: Optional[str] = None,
) -> List[dict]:
    """
    批量驾车路径规划

    Args:
        pairs: [((o_lng, o_lat), (d_lng, d_lat)), ...]
        api_key: 高德 API Key

    Returns:
        每条路径结果列表
    """
    direction = AmapDirection(api_key)
    results = []
    for origin, dest in pairs:
        try:
            result = direction.driving(origin, dest)
            results.append(result)
        except AmapDirectionError as e:
            results.append({
                "distance": 0.0,
                "duration": 0.0,
                "polyline": [],
                "status": 0,
                "error": str(e),
            })
    return results
