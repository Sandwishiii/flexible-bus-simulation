"""
距离矩阵预计算
站点间导航距离/时间的预计算与缓存
支持本地文件缓存（NavCache），避免重复调用高德 API
"""
from typing import List, Dict, Optional, Tuple
from core.stop import Stop
from utils.geo import haversine_distance
from utils.nav_cache import get_nav_cache


class DistanceMatrix:
    """
    站点间距离/时间矩阵

    支持两种模式:
    1. haversine: 直线距离（快速，无需 API）
    2. navigation: 导航距离（精确，需调用高德 API）

    用法:
        dm = DistanceMatrix(stops)
        dm.build(mode="haversine")
        dist = dm.get_distance("S001", "S005")  # 米
        time = dm.get_duration("S001", "S005")  # 秒
    """

    def __init__(self, stops: List[Stop], vehicle_speed: float = 30.0):
        """
        Args:
            stops: 站点列表
            vehicle_speed: 车辆平均速度 (km/h)，用于 haversine 模式下估算时间
        """
        self.stops = stops
        self.vehicle_speed = vehicle_speed

        # stop_id -> 索引
        self._id_to_idx: Dict[str, int] = {}
        for i, s in enumerate(stops):
            self._id_to_idx[s.stop_id] = i

        # 矩阵: n x n
        n = len(stops)
        self._dist_matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        self._time_matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        self._polyline_cache: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
        self._built = False

    def build(self, mode: str = "haversine", api_key: Optional[str] = None,
              progress_callback=None):
        """
        构建距离矩阵

        Args:
            mode: "haversine" (直线距离) 或 "navigation" (高德导航)
            api_key: 高德 API Key（navigation 模式必需）
            progress_callback: 可选的进度回调 callback(current, total, message)
        """
        n = len(self.stops)

        if mode == "haversine":
            self._build_haversine()
        elif mode == "navigation":
            self._build_navigation(api_key, progress_callback)
        else:
            raise ValueError(f"不支持的模式: {mode}")

        self._built = True

    def _build_haversine(self):
        """用 Haversine 直线距离构建矩阵"""
        n = len(self.stops)
        speed_ms = self.vehicle_speed / 3.6  # km/h -> m/s

        for i in range(n):
            for j in range(i + 1, n):
                dist = haversine_distance(
                    self.stops[i].lng, self.stops[i].lat,
                    self.stops[j].lng, self.stops[j].lat,
                )
                dur = dist / speed_ms if speed_ms > 0 else 0

                self._dist_matrix[i][j] = dist
                self._dist_matrix[j][i] = dist
                self._time_matrix[i][j] = dur
                self._time_matrix[j][i] = dur

    def _build_navigation(self, api_key: Optional[str] = None,
                           progress_callback=None):
        """用高德导航 API 构建距离矩阵（自动使用本地缓存）"""
        from utils.navigation import AmapDirection

        direction = AmapDirection(api_key, use_cache=True)
        n = len(self.stops)
        cache = get_nav_cache()

        # 计算总站点对数
        total_pairs = n * (n - 1) // 2
        current_pair = 0
        api_calls_before = cache.api_calls if cache else 0

        # 只对上半矩阵调 API（对称）
        for i in range(n):
            for j in range(i + 1, n):
                current_pair += 1
                origin = (self.stops[i].lng, self.stops[i].lat)
                dest = (self.stops[j].lng, self.stops[j].lat)
                try:
                    result = direction.driving(origin=origin, destination=dest)
                    dist = result["distance"]
                    dur = result["duration"]

                    self._dist_matrix[i][j] = dist
                    self._dist_matrix[j][i] = dist
                    self._time_matrix[i][j] = dur
                    self._time_matrix[j][i] = dur

                    # 缓存轨迹
                    if result.get("polyline"):
                        self._polyline_cache[(i, j)] = result["polyline"]
                        self._polyline_cache[(j, i)] = list(reversed(result["polyline"]))

                except Exception:
                    # API 失败时回退到 Haversine
                    dist = haversine_distance(
                        self.stops[i].lng, self.stops[i].lat,
                        self.stops[j].lng, self.stops[j].lat,
                    )
                    speed_ms = self.vehicle_speed / 3.6
                    dur = dist / speed_ms if speed_ms > 0 else 0

                    self._dist_matrix[i][j] = dist
                    self._dist_matrix[j][i] = dist
                    self._time_matrix[i][j] = dur
                    self._time_matrix[j][i] = dur

                # 进度回调
                if progress_callback:
                    try:
                        progress_callback(current_pair, total_pairs)
                    except Exception:
                        pass

        # 打印缓存统计
        actual_api_calls = (cache.api_calls if cache else 0) - api_calls_before
        if cache:
            stats = cache.stats()
            print(f"[DistanceMatrix] 导航缓存统计: "
                  f"{stats['total_entries']}条, "
                  f"命中率={stats['hit_rate']:.0f}%, "
                  f"本次API调用={actual_api_calls}次")

    def get_distance(self, stop_id_a: str, stop_id_b: str) -> float:
        """获取两站点间的距离（米）"""
        i = self._id_to_idx.get(stop_id_a)
        j = self._id_to_idx.get(stop_id_b)
        if i is None or j is None:
            # 未知站点，回退到 Haversine
            return 0.0
        return self._dist_matrix[i][j]

    def get_duration(self, stop_id_a: str, stop_id_b: str) -> float:
        """获取两站点间的行驶时间（秒）"""
        i = self._id_to_idx.get(stop_id_a)
        j = self._id_to_idx.get(stop_id_b)
        if i is None or j is None:
            return 0.0
        return self._time_matrix[i][j]

    def get_polyline(self, stop_id_a: str, stop_id_b: str) -> List[Tuple[float, float]]:
        """获取两站点间的导航轨迹坐标"""
        i = self._id_to_idx.get(stop_id_a)
        j = self._id_to_idx.get(stop_id_b)
        if i is None or j is None:
            return []
        return self._polyline_cache.get((i, j), [])

    def get_distance_by_coord(
        self,
        a: Tuple[float, float],
        b: Tuple[float, float],
    ) -> float:
        """通过坐标获取导航距离（先查缓存，再回退到 Haversine）"""
        cache = get_nav_cache()
        if cache:
            cached = cache.get(a, b)
            if cached:
                return cached['distance']
        return haversine_distance(a[0], a[1], b[0], b[1])

    def get_duration_by_coord(
        self,
        a: Tuple[float, float],
        b: Tuple[float, float],
    ) -> float:
        """通过坐标获取导航时间（先查缓存，再回退到速度估算）"""
        cache = get_nav_cache()
        if cache:
            cached = cache.get(a, b)
            if cached:
                return cached['duration']
        # 回退: Haversine 距离 / 速度
        dist = haversine_distance(a[0], a[1], b[0], b[1])
        speed_ms = self.vehicle_speed / 3.6
        return dist / speed_ms if speed_ms > 0 else 0

    def get_polyline_by_coord(
        self,
        a: Tuple[float, float],
        b: Tuple[float, float],
    ) -> List[Tuple[float, float]]:
        """通过坐标获取导航轨迹（先查缓存）"""
        cache = get_nav_cache()
        if cache:
            return cache.get_polyline(a, b)
        return []

    def find_nearest_stop(
        self,
        lng: float,
        lat: float,
    ) -> Optional[Stop]:
        """找到距离给定坐标最近的站点"""
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
    def is_built(self) -> bool:
        return self._built

    def get_summary(self) -> dict:
        """矩阵统计"""
        if not self._built:
            return {"built": False}

        n = len(self.stops)
        all_dists = []
        for i in range(n):
            for j in range(i + 1, n):
                all_dists.append(self._dist_matrix[i][j])

        return {
            "built": True,
            "n_stops": n,
            "n_pairs": len(all_dists),
            "avg_distance": sum(all_dists) / len(all_dists) if all_dists else 0,
            "max_distance": max(all_dists) if all_dists else 0,
            "min_distance": min(all_dists) if all_dists else 0,
        }
