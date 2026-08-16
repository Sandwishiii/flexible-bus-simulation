"""
全局配置文件
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List


class StopStrategy(Enum):
    """订单完成后车辆停靠策略"""
    IDLE_AT_LOCATION = auto()   # ① 就地待命
    CRUISE_TO_HOTSPOT = auto()  # ② 前往片区出行热力热点巡游
    RETURN_TO_DEPOT = auto()    # ③ 返回指定场站停放


@dataclass
class SimConfig:
    """仿真配置"""
    sim_start_time: int = 0
    sim_end_time: int = 86400
    base_hour: int = 6
    dispatch_batch_interval: float = 300.0
    max_dispatch_radius: float = 3000.0
    max_pickup_distance: float = 5000.0
    order_timeout_threshold: float = 1200.0
    max_wait_time: float = 1200.0
    max_direction_angle: float = 120.0
    nearby_stop_radius: float = 500.0
    load_balance_weight: float = 0.10
    vehicle_speed: float = 30.0
    vehicle_capacity: int = 20
    stop_stay_time: float = 30.0
    stop_strategy: StopStrategy = StopStrategy.IDLE_AT_LOCATION
    depot_lng: float = 0.0
    depot_lat: float = 0.0
    order_arrival_rate: float = 1.0
    weight_priority_1: float = 0.50
    weight_priority_2: float = 0.35
    weight_priority_3: float = 0.15
    weight_distance: float = 0.40
    weight_direction: float = 0.25
    weight_vehicle_status: float = 0.20
    weight_supply_demand: float = 0.15
    cost_per_km: float = 14.0


@dataclass
class CityConfig:
    """城市配置"""
    city_name: str = "杭州"
    city_code: str = "330100"
    amap_keys: list = None
    amap_key: Optional[str] = None

    def __post_init__(self):
        if self.amap_keys is None:
            self.amap_keys = [
                "b712ce5ea1b3073756e7c07036b7441a",
                "37fd775efb65461887a3b6b8f1610a19",
            ]
        if self.amap_key is None and self.amap_keys:
            self.amap_key = self.amap_keys[0]


sim_config = SimConfig()
city_config = CityConfig()
