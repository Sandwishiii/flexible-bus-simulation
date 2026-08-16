"""
车辆模型
定义车辆状态机与属性
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


class VehicleStatus(Enum):
    IDLE = auto()
    ENROUTE_PICKUP = auto()
    ARRIVED_PICKUP = auto()
    IN_SERVICE = auto()
    AT_STOP = auto()
    CRUISING = auto()
    OFF_DUTY = auto()
    FINISHED = auto()


@dataclass
class Vehicle:
    vehicle_id: str
    name: str = ""
    lng: float = 0.0
    lat: float = 0.0
    service_start_time: float = 0.0
    service_end_time: float = 86400.0
    capacity: int = 20
    current_passengers: int = 0
    status: VehicleStatus = VehicleStatus.IDLE
    assigned_order_ids: List[str] = field(default_factory=list)
    current_route: List[Tuple[float, float]] = field(default_factory=list)
    total_distance: float = 0.0
    total_orders: int = 0
    total_revenue: float = 0.0
    idle_time: float = 0.0
    pickup_distance: float = 0.0
    empty_distance: float = 0.0
    order_distance: float = 0.0

    def update_position(self, lng, lat, distance=0.0):
        self.lng = lng
        self.lat = lat
        self.total_distance += distance

    def assign_order(self, order_id):
        self.assigned_order_ids.append(order_id)

    def complete_order(self, order_id):
        if order_id in self.assigned_order_ids:
            self.assigned_order_ids.remove(order_id)
        self.total_orders += 1

    @property
    def is_available(self) -> bool:
        if self.status not in (VehicleStatus.IDLE, VehicleStatus.AT_STOP, VehicleStatus.CRUISING):
            return False
        if self.current_passengers >= self.capacity:
            return False
        return True

    @property
    def available_seats(self) -> int:
        return self.capacity - self.current_passengers
