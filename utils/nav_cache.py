"""
导航结果本地文件缓存
用本地 JSON 文件代替 Redis，缓存高德导航 API 的返回结果

缓存结构:
    cache/nav_cache.json  — 主缓存文件（dict）
    
缓存 key: "lng1,lat1_lng2,lat2"（坐标保留4位小数，约11m精度）

缓存 value:
    {
        "distance": 5688.0,      # 导航距离（米）
        "duration": 594.0,       # 导航时间（秒）
        "polyline": [[lng,lat], ...],  # 轨迹坐标
        "ts": 1234567890.0       # 缓存时间戳
    }
"""
import os
import json
import time
import atexit
import threading
from typing import Optional, Tuple, List, Dict


# 默认缓存目录
DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cache"
)

# 缓存过期时间（秒）：7天
CACHE_TTL = 7 * 24 * 3600

# 坐标精度（小数位数）
COORD_PRECISION = 4


class NavCache:
    """
    导航结果本地文件缓存
    
    用法:
        cache = NavCache()
        result = cache.get((106.76, 26.51), (106.79, 26.54))
        if result is None:
            result = call_amap_api(...)
            cache.set((106.76, 26.51), (106.79, 26.54), result)
    """

    # 自动刷写间隔（秒）：每 N 秒最多刷写一次
    FLUSH_INTERVAL = 5.0

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_file = os.path.join(self.cache_dir, "nav_cache.json")
        self._lock = threading.Lock()
        self._data: Dict[str, dict] = {}
        self._loaded = False
        self._dirty = False
        self._last_flush_time = time.time()

        # 统计
        self.hits = 0
        self.misses = 0
        self.api_calls = 0

    def _ensure_dir(self):
        """确保缓存目录存在"""
        os.makedirs(self.cache_dir, exist_ok=True)

    def _load(self):
        """从文件加载缓存（懒加载，首次访问时读取）"""
        if self._loaded:
            return
        self._ensure_dir()
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                print(f"[NavCache] 加载缓存: {len(self._data)} 条记录")
            except (json.JSONDecodeError, IOError) as e:
                print(f"[NavCache] 缓存文件损坏，重新开始: {e}")
                self._data = {}
        self._loaded = True

    def _save(self):
        """将缓存写入文件（仅在有更新且距离上次刷写超过间隔时）"""
        if not self._dirty:
            return
        # 延迟批量写入：避免每次 set 都重写文件
        now = time.time()
        if now - self._last_flush_time < self.FLUSH_INTERVAL:
            return
        self._flush_to_disk()

    def _flush_to_disk(self):
        """实际写入磁盘"""
        if not self._dirty:
            return
        self._ensure_dir()
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False)
            self._dirty = False
            self._last_flush_time = time.time()
        except IOError as e:
            print(f"[NavCache] 写入缓存失败: {e}")

    @staticmethod
    def _make_key(origin: Tuple[float, float],
                    destination: Tuple[float, float]) -> str:
        """生成缓存 key"""
        o_lng = round(origin[0], COORD_PRECISION)
        o_lat = round(origin[1], COORD_PRECISION)
        d_lng = round(destination[0], COORD_PRECISION)
        d_lat = round(destination[1], COORD_PRECISION)
        return f"{o_lng},{o_lat}_{d_lng},{d_lat}"

    def get(self, origin: Tuple[float, float],
            destination: Tuple[float, float]) -> Optional[dict]:
        """
        查询缓存
        
        Returns:
            {'distance': float, 'duration': float, 'polyline': [(lng,lat),...]} 或 None
        """
        with self._lock:
            self._load()
            key = self._make_key(origin, destination)
            entry = self._data.get(key)

            if entry is None:
                self.misses += 1
                return None

            # 检查过期
            ts = entry.get('ts', 0)
            if time.time() - ts > CACHE_TTL:
                del self._data[key]
                self._dirty = True
                self.misses += 1
                return None

            self.hits += 1
            return {
                'distance': entry['distance'],
                'duration': entry['duration'],
                'polyline': [tuple(p) for p in entry.get('polyline', [])],
            }

    def set(self, origin: Tuple[float, float],
            destination: Tuple[float, float],
            result: dict):
        """
        写入缓存
        
        Args:
            result: {'distance': float, 'duration': float, 'polyline': [(lng,lat),...]}
        """
        with self._lock:
            self._load()
            key = self._make_key(origin, destination)
            self._data[key] = {
                'distance': result['distance'],
                'duration': result['duration'],
                'polyline': [list(p) for p in result.get('polyline', [])],
                'ts': time.time(),
            }
            self._dirty = True
            self._save()

    def get_polyline(self, origin: Tuple[float, float],
                     destination: Tuple[float, float]) -> List[Tuple[float, float]]:
        """直接获取缓存的轨迹坐标"""
        result = self.get(origin, destination)
        if result:
            return result.get('polyline', [])
        return []

    def flush(self):
        """强制写入文件"""
        with self._lock:
            self._flush_to_disk()

    def stats(self) -> dict:
        """缓存统计"""
        with self._lock:
            self._load()
            return {
                'total_entries': len(self._data),
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': (self.hits / (self.hits + self.misses) * 100
                             if (self.hits + self.misses) > 0 else 0),
                'api_calls': self.api_calls,
                'cache_file': self.cache_file,
            }

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._data = {}
            self._dirty = True
            self._flush_to_disk()
            self.hits = 0
            self.misses = 0
            self.api_calls = 0


# 全局单例
_global_cache: Optional[NavCache] = None


def _atexit_flush():
    """程序退出时自动刷写缓存"""
    global _global_cache
    if _global_cache is not None:
        _global_cache.flush()


atexit.register(_atexit_flush)


def get_nav_cache(cache_dir: str = None) -> NavCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = NavCache(cache_dir)
    return _global_cache
