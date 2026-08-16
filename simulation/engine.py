"""
离散事件仿真引擎 (PEDS)
"""
import heapq
from typing import List, Dict, Optional, Tuple
from core.vehicle import Vehicle, VehicleStatus
from core.order import Order, OrderStatus
from core.stop import Stop
from dispatch.dispatcher import Dispatcher
from simulation.event import Event, EventType
from simulation.order_generator import OrderGenerator
from simulation.metrics import MetricsReport, compute_metrics
from utils.geo import haversine_distance
from config.settings import sim_config, StopStrategy


class SimEngine:
    def __init__(self, config=None):
        self.config = config or sim_config
        self.vehicles: List[Vehicle] = []
        self.stops: List[Stop] = []
        self.orders: List[Order] = []
        self.event_queue: List[Event] = []
        self.current_time: float = 0.0
        self.dispatcher = Dispatcher(max_pickup_distance=self.config.max_pickup_distance, max_direction_angle=self.config.max_direction_angle, nearby_stop_radius=self.config.nearby_stop_radius)
        self.order_generator = OrderGenerator(mode='random')
        self._pending_dispatch_orders: List[Order] = []
        self._last_dispatch_time: float = 0.0
        self._od_orders: List[Order] = []
        self._od_index: int = 0
        self._distance_matrix = None
        self._progress_callback = None
        self.trajectory_interval: float = 10.0
        self.trajectories: Dict[str, List[Tuple]] = {}
        self._vehicle_movements: Dict[str, dict] = {}
        self.stats = {'total_orders': 0, 'dispatched_orders': 0, 'completed_orders': 0, 'cancelled_orders': 0, 'timeout_orders': 0, 'total_wait_time': 0.0, 'total_ride_distance': 0.0, 'total_empty_distance': 0.0, 'total_order_distance': 0.0, 'max_concurrent_orders': 0, 'current_in_vehicle_orders': 0}
        self.metrics_report: Optional[MetricsReport] = None

    def add_vehicle(self, vehicle):
        self.vehicles.append(vehicle)
        self.trajectories[vehicle.vehicle_id] = []

    def add_stop(self, stop):
        self.stops.append(stop)

    def set_od_orders(self, orders):
        self._od_orders = sorted(orders, key=lambda o: o.request_time)
        self._od_index = 0

    def set_distance_matrix(self, dm):
        self._distance_matrix = dm

    def set_trajectory_interval(self, interval):
        self.trajectory_interval = max(1.0, interval)

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def setup(self):
        if not self._od_orders:
            self.order_generator.set_stops(self.stops)
            self.order_generator.set_arrival_rate(self.config.order_arrival_rate)
        self.trajectories = {}
        self._vehicle_movements = {}
        for vehicle in self.vehicles:
            self.trajectories[vehicle.vehicle_id] = []
        self._push_event(EventType.SIM_START, self.config.sim_start_time)
        t = self.config.sim_start_time
        while t < self.config.sim_end_time:
            self._push_event(EventType.DISPATCH_BATCH, t)
            t += self.config.dispatch_batch_interval
        t = self.config.sim_start_time
        while t <= self.config.sim_end_time:
            self._push_event(EventType.TRAJECTORY_RECORD, t)
            t += self.trajectory_interval
        self._push_event(EventType.SIM_END, self.config.sim_end_time)

    def run(self, verbose=True):
        self.setup()
        if verbose:
            mode = "OD回放" if self._od_orders else "随机生成"
            print(f"[仿真启动] 模式: {mode}, 时间范围: {self.config.sim_start_time} ~ {self.config.sim_end_time}s, 车辆: {len(self.vehicles)}, 站点: {len(self.stops)}")
            if self._od_orders:
                print(f"[仿真启动] 预加载订单: {len(self._od_orders)}")
        while self.event_queue:
            event = heapq.heappop(self.event_queue)
            self.current_time = event.time
            if event.event_type == EventType.SIM_END:
                if verbose:
                    print(f"\n[仿真结束] 当前时间: {self.current_time:.1f}s")
                break
            if self._progress_callback and event.event_type == EventType.DISPATCH_BATCH:
                try:
                    self._progress_callback(self.current_time)
                except Exception:
                    pass
            self._handle_event(event, verbose)
        sim_duration = self.config.sim_end_time - self.config.sim_start_time
        self.metrics_report = compute_metrics(vehicles=self.vehicles, orders=self.orders, stats=self.stats, sim_duration=sim_duration, cost_per_km=self.config.cost_per_km)
        if verbose:
            self.print_stats()
        return self.stats

    def _handle_event(self, event, verbose=False):
        handler_map = {EventType.SIM_START: self._on_sim_start, EventType.DISPATCH_BATCH: self._on_dispatch_batch, EventType.ORDER_CREATED: self._on_order_created, EventType.ORDER_PICKUP: self._on_order_pickup, EventType.ORDER_COMPLETE: self._on_order_complete, EventType.ORDER_TIMEOUT: self._on_order_timeout, EventType.TRAJECTORY_RECORD: self._on_trajectory_record}
        handler = handler_map.get(event.event_type)
        if handler:
            handler(event, verbose)

    def _on_sim_start(self, event, verbose):
        if verbose:
            print(f"[{event.time:.1f}s] 仿真开始")

    def _on_dispatch_batch(self, event, verbose):
        new_orders = self._get_new_orders(self.current_time, self.config.dispatch_batch_interval)
        for order in new_orders:
            self.orders.append(order)
            self.stats['total_orders'] += 1
            timeout_time = order.request_time + self.config.order_timeout_threshold
            self._push_event(EventType.ORDER_TIMEOUT, timeout_time, data=order)
        pending = [o for o in self.orders if o.status == OrderStatus.PENDING]
        if pending and self.vehicles:
            results = self.dispatcher.dispatch(self.vehicles, pending, self.current_time, vehicle_speed=self.config.vehicle_speed)
            self.stats['dispatched_orders'] += len(results)
            if verbose and results:
                print(f"[{event.time:.1f}s] 派单: {len(results)} 单匹配成功 (待分配: {len(pending)})")
            for vehicle, order, score in results:
                pickup_dist = haversine_distance(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
                pickup_time = self._estimate_pickup_time(vehicle, order)
                if pickup_time > 0:
                    self._record_movement(vehicle.vehicle_id, vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat, self.current_time, self.current_time + pickup_time, move_dist=pickup_dist, status_name="ENROUTE_PICKUP")
                self._push_event(EventType.ORDER_PICKUP, self.current_time + pickup_time, data={'vehicle_id': vehicle.vehicle_id, 'order_id': order.order_id})

    def _get_new_orders(self, current_time, time_step):
        if self._od_orders:
            orders = []
            while self._od_index < len(self._od_orders):
                order = self._od_orders[self._od_index]
                if order.request_time <= current_time + time_step:
                    orders.append(order)
                    self._od_index += 1
                else:
                    break
            return orders
        else:
            return self.order_generator.generate(current_time, time_step)

    def _on_order_created(self, event, verbose):
        order = event.data
        self.orders.append(order)
        self.stats['total_orders'] += 1

    def _record_movement(self, vehicle_id, from_lng, from_lat, to_lng, to_lat, start_time, end_time, move_dist=0.0, status_name="ENROUTE_PICKUP"):
        self._vehicle_movements[vehicle_id] = {'from_lng': from_lng, 'from_lat': from_lat, 'to_lng': to_lng, 'to_lat': to_lat, 'start_time': start_time, 'end_time': end_time, 'move_dist': move_dist, 'status': status_name}

    def _finalize_movement(self, vehicle_id, up_to_time=None):
        mv = self._vehicle_movements.pop(vehicle_id, None)
        if not mv:
            return 0.0, 0.0, 0.0
        vehicle = self._find_vehicle(vehicle_id)
        if vehicle:
            vehicle.lng = mv['to_lng']
            vehicle.lat = mv['to_lat']
        return mv['to_lng'], mv['to_lat'], mv['move_dist']

    def _get_interpolated_position(self, vehicle_id, time):
        mv = self._vehicle_movements.get(vehicle_id)
        if not mv:
            return None
        if time <= mv['start_time']:
            return (mv['from_lng'], mv['from_lat'], mv['status'])
        if time >= mv['end_time']:
            return (mv['to_lng'], mv['to_lat'], mv['status'])
        progress = (time - mv['start_time']) / (mv['end_time'] - mv['start_time'])
        lng = mv['from_lng'] + (mv['to_lng'] - mv['from_lng']) * progress
        lat = mv['from_lat'] + (mv['to_lat'] - mv['from_lat']) * progress
        return (lng, lat, mv['status'])

    def _on_order_pickup(self, event, verbose):
        data = event.data
        vehicle = self._find_vehicle(data['vehicle_id'])
        order = self._find_order(data['order_id'])
        if not vehicle or not order or order.status != OrderStatus.DISPATCHED:
            return
        _, _, pickup_dist = self._finalize_movement(vehicle.vehicle_id)
        if pickup_dist == 0.0:
            pickup_dist = haversine_distance(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
        order.pickup(self.current_time)
        order.pickup_distance = pickup_dist
        vehicle.empty_distance += pickup_dist
        vehicle.current_passengers += order.passenger_count
        vehicle.status = VehicleStatus.IN_SERVICE
        self.stats['current_in_vehicle_orders'] += 1
        if self.stats['current_in_vehicle_orders'] > self.stats['max_concurrent_orders']:
            self.stats['max_concurrent_orders'] = self.stats['current_in_vehicle_orders']
        ride_distance = self._get_ride_distance(order)
        ride_time = self._get_ride_time(ride_distance)
        if ride_time > 0:
            self._record_movement(vehicle.vehicle_id, order.origin_lng, order.origin_lat, order.dest_lng, order.dest_lat, self.current_time, self.current_time + ride_time, move_dist=ride_distance, status_name="IN_SERVICE")
        self._push_event(EventType.ORDER_COMPLETE, self.current_time + ride_time, data={'vehicle_id': vehicle.vehicle_id, 'order_id': order.order_id, 'ride_distance': ride_distance})

    def _on_order_complete(self, event, verbose):
        data = event.data
        vehicle = self._find_vehicle(data['vehicle_id'])
        order = self._find_order(data['order_id'])
        if not vehicle or not order:
            return
        ride_distance = data.get('ride_distance', 0)
        order.complete(self.current_time, ride_distance)
        vehicle.complete_order(order.order_id)
        vehicle.current_passengers -= order.passenger_count
        vehicle.total_distance += ride_distance
        vehicle.order_distance += ride_distance
        self._finalize_movement(vehicle.vehicle_id)
        self.stats['completed_orders'] += 1
        self.stats['total_wait_time'] += order.wait_time
        self.stats['total_ride_distance'] += ride_distance
        self.stats['current_in_vehicle_orders'] = max(0, self.stats['current_in_vehicle_orders'] - 1)
        if not vehicle.assigned_order_ids:
            self._apply_stop_strategy(vehicle)

    def _on_order_timeout(self, event, verbose):
        order = event.data
        if order.status == OrderStatus.PENDING:
            order.status = OrderStatus.TIMEOUT
            self.stats['timeout_orders'] += 1

    def _on_trajectory_record(self, event, verbose):
        for vehicle in self.vehicles:
            vid = vehicle.vehicle_id
            if vid not in self.trajectories:
                self.trajectories[vid] = []
            stats = (vehicle.current_passengers, vehicle.total_orders, round(vehicle.total_distance, 1))
            mv = self._vehicle_movements.get(vid)
            if mv:
                if self.current_time >= mv['end_time']:
                    end_time = mv['end_time']
                    self.trajectories[vid].append((end_time, mv['to_lng'], mv['to_lat'], mv['status'], stats[0], stats[1], stats[2]))
                    self._finalize_movement(vid)
                    if self.current_time > end_time:
                        self.trajectories[vid].append((self.current_time, vehicle.lng, vehicle.lat, vehicle.status.name, stats[0], stats[1], stats[2]))
                else:
                    pos = self._get_interpolated_position(vid, self.current_time)
                    if pos:
                        self.trajectories[vid].append((self.current_time, pos[0], pos[1], pos[2], stats[0], stats[1], stats[2]))
                    else:
                        self.trajectories[vid].append((self.current_time, vehicle.lng, vehicle.lat, vehicle.status.name, stats[0], stats[1], stats[2]))
            else:
                self.trajectories[vid].append((self.current_time, vehicle.lng, vehicle.lat, vehicle.status.name, stats[0], stats[1], stats[2]))

    def _apply_stop_strategy(self, vehicle):
        strategy = self.config.stop_strategy
        if strategy == StopStrategy.IDLE_AT_LOCATION:
            vehicle.status = VehicleStatus.IDLE
        elif strategy == StopStrategy.CRUISE_TO_HOTSPOT:
            if self.stops:
                import random
                hotspot = random.choice(self.stops)
                cruise_dist = haversine_distance(vehicle.lng, vehicle.lat, hotspot.lng, hotspot.lat)
                speed_ms = self.config.vehicle_speed / 3.6
                cruise_time = cruise_dist / speed_ms if speed_ms > 0 else 0
                if cruise_time > 0:
                    self._record_movement(vehicle.vehicle_id, vehicle.lng, vehicle.lat, hotspot.lng, hotspot.lat, self.current_time, self.current_time + cruise_time, move_dist=cruise_dist, status_name="CRUISING")
                else:
                    vehicle.lng = hotspot.lng
                    vehicle.lat = hotspot.lat
                vehicle.empty_distance += cruise_dist
                vehicle.total_distance += cruise_dist
                vehicle.status = VehicleStatus.CRUISING
            else:
                vehicle.status = VehicleStatus.IDLE
        elif strategy == StopStrategy.RETURN_TO_DEPOT:
            if self.config.depot_lng != 0.0 or self.config.depot_lat != 0.0:
                depot_dist = haversine_distance(vehicle.lng, vehicle.lat, self.config.depot_lng, self.config.depot_lat)
                speed_ms = self.config.vehicle_speed / 3.6
                depot_time = depot_dist / speed_ms if speed_ms > 0 else 0
                if depot_time > 0:
                    self._record_movement(vehicle.vehicle_id, vehicle.lng, vehicle.lat, self.config.depot_lng, self.config.depot_lat, self.current_time, self.current_time + depot_time, move_dist=depot_dist, status_name="IDLE")
                else:
                    vehicle.lng = self.config.depot_lng
                    vehicle.lat = self.config.depot_lat
                vehicle.empty_distance += depot_dist
                vehicle.total_distance += depot_dist
            vehicle.status = VehicleStatus.IDLE

    def _estimate_pickup_time(self, vehicle, order):
        distance = self._calc_distance(vehicle.lng, vehicle.lat, order.origin_lng, order.origin_lat)
        speed_ms = self.config.vehicle_speed / 3.6
        return distance / speed_ms if speed_ms > 0 else 0

    def _calc_distance(self, lng1, lat1, lng2, lat2):
        if self._distance_matrix:
            stop_a = self._distance_matrix.find_nearest_stop(lng1, lat1)
            stop_b = self._distance_matrix.find_nearest_stop(lng2, lat2)
            if stop_a and stop_b and stop_a.stop_id != stop_b.stop_id:
                dist = self._distance_matrix.get_distance(stop_a.stop_id, stop_b.stop_id)
                if dist > 0:
                    return dist
        return haversine_distance(lng1, lat1, lng2, lat2)

    def _get_ride_distance(self, order):
        if self._distance_matrix and order.origin_stop_id and order.dest_stop_id:
            dist = self._distance_matrix.get_distance(order.origin_stop_id, order.dest_stop_id)
            if dist > 0:
                return dist
        return haversine_distance(order.origin_lng, order.origin_lat, order.dest_lng, order.dest_lat)

    def _get_ride_time(self, ride_distance):
        speed_ms = self.config.vehicle_speed / 3.6
        return ride_distance / speed_ms if speed_ms > 0 else 0

    def _push_event(self, event_type, time, data=None):
        event = Event(event_type=event_type, time=time, data=data)
        heapq.heappush(self.event_queue, event)

    def _find_vehicle(self, vehicle_id):
        for v in self.vehicles:
            if v.vehicle_id == vehicle_id:
                return v
        return None

    def _find_order(self, order_id):
        for o in self.orders:
            if o.order_id == order_id:
                return o
        return None

    def get_trajectories_json(self):
        result = {}
        for vid, points in self.trajectories.items():
            result[vid] = [[p[0], round(p[1], 6), round(p[2], 6), p[3], p[4] if len(p) > 4 else 0, p[5] if len(p) > 5 else 0, p[6] if len(p) > 6 else 0] for p in points]
        return result

    def print_stats(self):
        if self.metrics_report:
            print(self.metrics_report.to_text())
        else:
            print("\n" + "=" * 50)
            print("仿真统计结果")
            print("=" * 50)
            print(f"总订单数:       {self.stats['total_orders']}")
            print(f"已派单数:       {self.stats['dispatched_orders']}")
            print(f"已完成数:       {self.stats['completed_orders']}")
            print(f"超时未应答:     {self.stats['timeout_orders']}")
            print("=" * 50)
