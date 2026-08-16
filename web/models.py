"""
Pydantic 模型定义
API 请求/响应的数据结构
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class StopStrategyEnum(str, Enum):
    IDLE_AT_LOCATION = "idle"
    CRUISE_TO_HOTSPOT = "cruise"
    RETURN_TO_DEPOT = "depot"


class TimeDistributionEnum(str, Enum):
    UNIFORM = "uniform"
    PEAK_WEIGHTED = "peak_weighted"


class SimParams(BaseModel):
    sim_start_hour: int = Field(default=6, ge=0, le=23)
    sim_duration_hours: float = Field(default=1.0, gt=0, le=24)
    dispatch_interval: float = Field(default=30.0, ge=1, le=600)
    max_pickup_distance: float = Field(default=3000.0, ge=100, le=20000)
    max_direction_angle: float = Field(default=120.0, ge=0, le=180)
    order_timeout: float = Field(default=1200.0, ge=60, le=7200)
    vehicle_count: int = Field(default=5, ge=1, le=100)
    vehicle_speed: float = Field(default=30.0, ge=5, le=80)
    vehicle_capacity: int = Field(default=20, ge=1, le=60)
    cost_per_km: float = Field(default=14.0, ge=0)
    stop_strategy: StopStrategyEnum = Field(default=StopStrategyEnum.IDLE_AT_LOCATION)
    trajectory_interval: float = Field(default=10.0, ge=1, le=60)
    distance_mode: str = Field(default="haversine")


class VehicleInitPosition(BaseModel):
    vehicle_id: str = ""
    name: str = ""
    lng: float
    lat: float


class ODUploadResponse(BaseModel):
    total_records: int
    total_demand: int
    avg_demand: float
    format: str
    o_lng_range: List[float]
    o_lat_range: List[float]
    d_lng_range: List[float]
    d_lat_range: List[float]
    od_records: List[Dict] = []
    truncated: bool = False


class StationUploadResponse(BaseModel):
    total_stops: int
    total_routes: int
    routes: List[str]
    stops: List[Dict]


class RegionUploadResponse(BaseModel):
    vertex_count: int
    bbox: List[float]
    vertices: List[List[float]]


class ODExpandParams(BaseModel):
    time_distribution: TimeDistributionEnum = TimeDistributionEnum.UNIFORM
    peak_start_hour: float = Field(default=7.0)
    peak_end_hour: float = Field(default=9.0)
    peak_weight: float = Field(default=3.0, ge=1, le=10)
    max_orders: int = Field(default=-1)
    sim_start_hour: float = Field(default=6.0)
    sim_end_hour: float = Field(default=7.0)


class MetricsReportResponse(BaseModel):
    total_orders: int
    dispatched_orders: int
    completed_orders: int
    timeout_orders: int
    completion_rate: float
    timeout_rate: float
    avg_wait_time: float
    avg_ride_time: float
    avg_ride_distance: float
    avg_pickup_distance: float
    max_concurrent_orders: int
    total_vehicle_distance: float
    total_order_distance: float
    total_empty_distance: float
    empty_rate: float
    orders_per_100km: float
    carpool_intensity: float
    total_cost: float
    cost_per_passenger: float
    sim_duration: float
    vehicle_count: int


class SimulateRequest(BaseModel):
    params: SimParams
    od_expand: ODExpandParams
    vehicles: List[VehicleInitPosition] = []


class SimulateResponse(BaseModel):
    run_id: str
    status: str
    metrics: MetricsReportResponse
    message: str = ""


class TrajectoryResponse(BaseModel):
    run_id: str
    trajectories: Dict[str, List[List]]


class SimProgressResponse(BaseModel):
    status: str
    progress: float = 0.0
    message: str = ""
    run_id: str = ""
    metrics: Optional[MetricsReportResponse] = None
