"""
派单调度器
三层优先级：
  1. 保障车内乘客，优先顺路车辆，压缩乘车时长
  2. 缩短候车时间，匹配距离最近运力
  3. 控制车辆投入，减少空载里程
"""
from typing import List, Dict, Tuple, Optional
from core.vehicle import Vehicle, VehicleStatus
from core.order import Order, OrderStatus
from dispatch.scorer import DispatchScorer
from dispatch.matcher import BipartiteMatcher
from utils.geo import haversine_distance


class Dispatcher:
    def __init__(self, max_pickup_distance=5000.0, max_direction_angle=120.0,
                 nearby_stop_radius=500.0, match_method='km', scorer_weights=None):
        self.max_pickup_distance = max_pickup_distance
        self.scorer = DispatchScorer(weights=scorer_weights)
        self.scorer.max_direction_angle = max_direction_angle
        self.scorer.nearby_stop_radius = nearby_stop_radius
        self.matcher = BipartiteMatcher(method=match_method)
        self.total_dispatch_count = 0
        self.total_dispatch_history = []

    def dispatch(self, vehicles, orders, current_time, vehicle_speed=30.0, supply_demand_map=None):
        available_vehicles = [v for v in vehicles if v.is_available]
        pending_orders = [o for o in orders if o.status == OrderStatus.PENDING]
        if not available_vehicles or not pending_orders:
            return []
        filtered_vehicles, filtered_orders, filtered_mask = self._filter_pairs(available_vehicles, pending_orders)
        if not filtered_vehicles or not filtered_orders:
            return []
        score_matrix = self.scorer.build_score_matrix(filtered_vehicles, filtered_orders, current_time=current_time, vehicle_speed=vehicle_speed, supply_demand_map=supply_demand_map)
        for i in range(len(filtered_vehicles)):
            for j in range(len(filtered_orders)):
                if not filtered_mask[i][j]:
                    score_matrix[i][j] = 0.0
        matches = self.matcher.match(score_matrix)
        results = []
        for v_idx, o_idx, score in matches:
            vehicle = filtered_vehicles[v_idx]
            order = filtered_orders[o_idx]
            pickup_dist = haversine_distance(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
            ride_dist = haversine_distance(order.origin_lng, order.origin_lat, order.dest_lng, order.dest_lat)
            speed_ms = vehicle_speed / 3.6
            estimated_wait = pickup_dist / speed_ms if speed_ms > 0 else 0
            estimated_ride = ride_dist / speed_ms if speed_ms > 0 else 0
            order.dispatch_to(vehicle.vehicle_id, current_time, estimated_wait=estimated_wait, estimated_ride=estimated_ride)
            order.pickup_distance = pickup_dist
            order.estimated_ride_distance = ride_dist
            vehicle.assign_order(order.order_id)
            vehicle.status = VehicleStatus.ENROUTE_PICKUP
            results.append((vehicle, order, score))
            self.total_dispatch_count += 1
        if results:
            self.total_dispatch_history.append({'time': current_time, 'matches': len(results), 'details': [{'vehicle_id': v.vehicle_id, 'order_id': o.order_id, 'score': s} for v, o, s in results]})
        return results

    def _filter_pairs(self, vehicles, orders):
        mask = [[True] * len(orders) for _ in range(len(vehicles))]
        valid_vehicles = []
        valid_orders = []
        v_map = {}
        o_map = {}
        for i, v in enumerate(vehicles):
            has_valid = False
            for j, o in enumerate(orders):
                dist = haversine_distance(v.lng, v.lat, o.origin_lng, o.origin_lat)
                if dist > self.max_pickup_distance:
                    mask[i][j] = False
                    continue
                if v.available_seats < o.passenger_count:
                    mask[i][j] = False
                    continue
                if not self.scorer._check_direction_constraint(v, o):
                    mask[i][j] = False
                    continue
                has_valid = True
            if has_valid:
                v_map[i] = len(valid_vehicles)
                valid_vehicles.append(vehicles[i])
        for j, o in enumerate(orders):
            has_valid = any(mask[i][j] for i in range(len(vehicles)))
            if has_valid:
                o_map[j] = len(valid_orders)
                valid_orders.append(orders[j])
        new_mask = [[False] * len(valid_orders) for _ in range(len(valid_vehicles))]
        for i in range(len(vehicles)):
            for j in range(len(orders)):
                if i in v_map and j in o_map and mask[i][j]:
                    new_mask[v_map[i]][o_map[j]] = True
        return valid_vehicles, valid_orders, new_mask
