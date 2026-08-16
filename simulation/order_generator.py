"""
订单生成器
"""
import random
import numpy as np
from typing import List, Optional, Dict
from core.order import Order
from core.stop import Stop


class OrderGenerator:
    def __init__(self, mode='random', seed=42):
        assert mode in ('history', 'random', 'custom')
        self.mode = mode
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed)
        self.arrival_rate = 1.0
        self.stops: List[Stop] = []
        self.history_orders: List[Dict] = []
        self.history_index = 0

    def set_stops(self, stops):
        self.stops = stops

    def set_arrival_rate(self, rate):
        self.arrival_rate = rate

    def load_history(self, orders_data):
        self.history_orders = sorted(orders_data, key=lambda x: x.get('request_time', 0))
        self.history_index = 0

    def generate(self, current_time, time_step):
        if self.mode == 'random':
            return self._generate_random(current_time, time_step)
        elif self.mode == 'history':
            return self._generate_history(current_time)
        else:
            return []

    def _generate_random(self, current_time, time_step):
        if not self.stops or len(self.stops) < 2:
            return []
        expected = self.arrival_rate * time_step / 60.0
        n_orders = self.np_rng.poisson(expected)
        orders = []
        for _ in range(n_orders):
            origin_stop = self.rng.choice(self.stops)
            dest_stop = self.rng.choice(self.stops)
            while dest_stop.stop_id == origin_stop.stop_id:
                dest_stop = self.rng.choice(self.stops)
            order = Order(origin_lng=origin_stop.lng, origin_lat=origin_stop.lat, origin_stop_id=origin_stop.stop_id, origin_stop_name=origin_stop.name, dest_lng=dest_stop.lng, dest_lat=dest_stop.lat, dest_stop_id=dest_stop.stop_id, dest_stop_name=dest_stop.name, request_time=current_time + self.rng.uniform(0, time_step), passenger_count=self.rng.randint(1, 3))
            orders.append(order)
        return orders

    def _generate_history(self, current_time):
        orders = []
        while self.history_index < len(self.history_orders):
            record = self.history_orders[self.history_index]
            req_time = record.get('request_time', 0)
            if req_time > current_time:
                break
            order = Order(origin_lng=record.get('origin_lng', 0), origin_lat=record.get('origin_lat', 0), origin_stop_id=record.get('origin_stop_id'), origin_stop_name=record.get('origin_stop_name', ''), dest_lng=record.get('dest_lng', 0), dest_lat=record.get('dest_lat', 0), dest_stop_id=record.get('dest_stop_id'), dest_stop_name=record.get('dest_stop_name', ''), request_time=req_time, passenger_count=record.get('passenger_count', 1))
            orders.append(order)
            self.history_index += 1
        return orders
