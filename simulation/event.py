"""
事件定义
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class EventType(Enum):
    ORDER_CREATED = auto()
    ORDER_DISPATCHED = auto()
    ORDER_PICKUP = auto()
    ORDER_COMPLETE = auto()
    ORDER_TIMEOUT = auto()
    VEHICLE_ARRIVE_STOP = auto()
    VEHICLE_DEPART = auto()
    VEHICLE_GO_IDLE = auto()
    DISPATCH_BATCH = auto()
    SIM_START = auto()
    SIM_END = auto()
    TRAJECTORY_RECORD = auto()


@dataclass
class Event:
    event_type: EventType
    time: float
    data: Any = None
    priority: int = 0

    def __lt__(self, other):
        if self.time != other.time:
            return self.time < other.time
        return self.priority > other.priority
