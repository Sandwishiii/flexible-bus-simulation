"""
司乘评分计算
三层优先级多目标动态派单算法
"""
import math
from typing import Dict, List, Tuple, Optional
from core.vehicle import Vehicle, VehicleStatus
from core.order import Order
from utils.geo import haversine_distance, calc_bearing


class DispatchScorer:
    def __init__(self, weights=None):
        self.weights = weights or {'priority_1': 0.50, 'priority_2': 0.35, 'priority_3': 0.15}
        self.max_direction_angle = 120.0
        self.nearby_stop_radius = 500.0

    def calc_score(self, vehicle, order, current_time=0.0, vehicle_speed=30.0, load_balance_factor=0.0):
        if not self._check_direction_constraint(vehicle, order):
            return 0.0
        p1_score = self._calc_priority_1(vehicle, order, vehicle_speed)
        p2_score = self._calc_priority_2(vehicle, order, vehicle_speed)
        p3_score = self._calc_priority_3(vehicle, order)
        lb_penalty = 1.0 - load_balance_factor * 0.3
        total_score = (self.weights['priority_1'] * p1_score + self.weights['priority_2'] * p2_score + self.weights['priority_3'] * p3_score) * lb_penalty
        return max(0.0, min(1.0, total_score))

    def _check_direction_constraint(self, vehicle, order):
        if len(vehicle.current_route) < 2:
            return True
        prev_lng, prev_lat = vehicle.current_route[-2]
        vehicle_bearing = calc_bearing(prev_lng, prev_lat, vehicle.lng, vehicle.lat)
        to_order_bearing = calc_bearing(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
        angle_diff = abs(vehicle_bearing - to_order_bearing) % 360
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        return angle_diff <= self.max_direction_angle

    def _calc_priority_1(self, vehicle, order, vehicle_speed):
        direction_score = self._calc_direction_score(vehicle, order)
        if vehicle.current_passengers == 0:
            passenger_score = 1.0
        else:
            pickup_dist = haversine_distance(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
            passenger_score = 1.0 / (1.0 + pickup_dist / 1000.0)
        return 0.6 * direction_score + 0.4 * passenger_score

    def _calc_priority_2(self, vehicle, order, vehicle_speed):
        pickup_distance = haversine_distance(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
        d0 = 1000.0
        score = 1.0 / (1.0 + pickup_distance / d0)
        return score

    def _calc_priority_3(self, vehicle, order):
        if vehicle.status == VehicleStatus.IN_SERVICE:
            return 0.9
        elif vehicle.status == VehicleStatus.ENROUTE_PICKUP:
            return 0.7
        elif vehicle.status in (VehicleStatus.IDLE, VehicleStatus.AT_STOP, VehicleStatus.CRUISING):
            return 0.5
        return 0.3

    def _calc_direction_score(self, vehicle, order):
        if len(vehicle.current_route) < 2:
            return 0.5
        prev_lng, prev_lat = vehicle.current_route[-2]
        vehicle_bearing = calc_bearing(prev_lng, prev_lat, vehicle.lng, vehicle.lat)
        order_bearing = calc_bearing(order.origin_lng, order.origin_lat, order.dest_lng, order.dest_lat)
        angle_diff = abs(vehicle_bearing - order_bearing) % 360
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        score = 1.0 - angle_diff / 180.0
        return score

    def build_score_matrix(self, vehicles, orders, current_time=0.0, vehicle_speed=30.0, supply_demand_map=None):
        n_vehicles = len(vehicles)
        n_orders = len(orders)
        matrix = [[0.0] * n_orders for _ in range(n_vehicles)]
        max_orders = max((len(v.assigned_order_ids) for v in vehicles), default=1)
        for i, vehicle in enumerate(vehicles):
            for j, order in enumerate(orders):
                lb_factor = len(vehicle.assigned_order_ids) / max(max_orders, 1)
                matrix[i][j] = self.calc_score(vehicle, order, current_time, vehicle_speed, lb_factor)
        return matrix
