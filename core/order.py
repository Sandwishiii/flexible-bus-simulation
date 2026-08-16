"""
订单模型
定义订单属性与状态流转
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import uuid


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = auto()
    DISPATCHED = auto()
    PICKED_UP = auto()
    IN_TRANSIT = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    TIMEOUT = auto()


@dataclass
class Order:
    """
    订单模型
    状态流转: PENDING -> DISPATCHED -> PICKED_UP -> IN_TRANSIT -> COMPLETED
    """
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    origin_lng: float = 0.0
    origin_lat: float = 0.0
    origin_stop_id: Optional[str] = None
    origin_stop_name: str = ""
    dest_lng: float = 0.0
    dest_lat: float = 0.0
    dest_stop_id: Optional[str] = None
    dest_stop_name: str = ""
    request_time: float = 0.0
    dispatch_time: Optional[float] = None
    pickup_time: Optional[float] = None
    complete_time: Optional[float] = None
    assigned_vehicle_id: Optional[str] = None
    passenger_count: int = 1
    status: OrderStatus = OrderStatus.PENDING
    route_stop_ids: List[str] = field(default_factory=list)
    wait_time: float = 0.0
    estimated_wait_time: float = 0.0
    pickup_distance: float = 0.0
    ride_distance: float = 0.0
    estimated_ride_distance: float = 0.0
    ride_duration: float = 0.0
    estimated_ride_duration: float = 0.0
    detour_distance: float = 0.0
    total_order_duration: float = 0.0

    @property
    def straight_line_distance(self) -> float:
        from utils.geo import haversine_distance
        return haversine_distance(self.origin_lng, self.origin_lat, self.dest_lng, self.dest_lat)

    def dispatch_to(self, vehicle_id, dispatch_time, estimated_wait=0.0, estimated_ride=0.0):
        self.assigned_vehicle_id = vehicle_id
        self.dispatch_time = dispatch_time
        self.status = OrderStatus.DISPATCHED
        self.wait_time = dispatch_time - self.request_time
        self.estimated_wait_time = estimated_wait
        self.estimated_ride_duration = estimated_ride

    def pickup(self, pickup_time):
        self.pickup_time = pickup_time
        self.status = OrderStatus.PICKED_UP

    def start_transit(self):
        self.status = OrderStatus.IN_TRANSIT

    def complete(self, complete_time, ride_distance=0.0):
        self.complete_time = complete_time
        self.ride_distance = ride_distance
        self.ride_duration = complete_time - (self.pickup_time or complete_time)
        self.total_order_duration = complete_time - self.request_time
        self.detour_distance = max(0, ride_distance - self.straight_line_distance)
        self.status = OrderStatus.COMPLETED

    def cancel(self):
        self.status = OrderStatus.CANCELLED
