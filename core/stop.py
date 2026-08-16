from dataclasses import dataclass, field
from typing import Optional, Tuple, List


@dataclass
class Stop:
    """公交站点模型"""
    stop_id: str
    name: str = ""
    lng: float = 0.0
    lat: float = 0.0
    is_active: bool = True
    total_pickups: int = 0
    total_dropoffs: int = 0

    def distance_to(self, other_lng: float, other_lat: float) -> float:
        from utils.geo import haversine_distance
        return haversine_distance(self.lng, self.lat, other_lng, other_lat)

    @property
    def coordinate(self) -> Tuple[float, float]:
        return (self.lng, self.lat)

    def __repr__(self):
        return f"Stop({self.stop_id}, {self.name}, pos=({self.lng:.4f},{self.lat:.4f}))"
