"""
灵活公交仿真平台 - 主入口
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.vehicle import Vehicle, VehicleStatus
from core.stop import Stop
from simulation.engine import SimEngine
from config.settings import sim_config


def create_demo_stops():
    stops = [
        Stop(stop_id='S001', name='西溪白荻苑', lng=120.06207, lat=30.28475),
        Stop(stop_id='S002', name='蒋村法昌寺', lng=120.062347, lat=30.291484),
        Stop(stop_id='S003', name='西溪水岸北', lng=120.050991, lat=30.286091),
        Stop(stop_id='S004', name='杨家埭', lng=120.057206, lat=30.292294),
        Stop(stop_id='S005', name='蒋家蚌桥', lng=120.05958, lat=30.28966),
        Stop(stop_id='S006', name='西溪竞舟苑', lng=120.057948, lat=30.282511),
        Stop(stop_id='S007', name='何家坝', lng=120.05437, lat=30.28667),
        Stop(stop_id='S008', name='朝天莫港桥', lng=120.06075, lat=30.27985),
        Stop(stop_id='S009', name='枫树湾河桥', lng=120.062889, lat=30.286653),
        Stop(stop_id='S010', name='古荡', lng=120.122253, lat=30.271856),
        Stop(stop_id='S011', name='文二西路丰潭路口', lng=120.110227, lat=30.281855),
        Stop(stop_id='S012', name='天苑花园', lng=120.12226, lat=30.2764),
    ]
    return stops


def create_demo_vehicles(n_vehicles=5, stops=None):
    vehicles = []
    for i in range(n_vehicles):
        stop = stops[i % len(stops)]
        vehicle = Vehicle(vehicle_id=f'V{i+1:03d}', name=f'云公交{i+1}号', lng=stop.lng, lat=stop.lat, capacity=sim_config.vehicle_capacity, service_start_time=0, service_end_time=86400)
        vehicles.append(vehicle)
    return vehicles


def main():
    print("=" * 50)
    print("   灵活公交仿真平台 v0.1")
    print("   基于网约车派单算法 (二分图匹配)")
    print("=" * 50)

    sim_config.sim_start_time = 0
    sim_config.sim_end_time = 3600
    sim_config.dispatch_batch_interval = 5
    sim_config.vehicle_speed = 30.0
    sim_config.order_arrival_rate = 3.0
    sim_config.max_pickup_distance = 3000

    engine = SimEngine(config=sim_config)
    stops = create_demo_stops()
    for stop in stops:
        engine.add_stop(stop)
    vehicles = create_demo_vehicles(n_vehicles=5, stops=stops)
    for v in vehicles:
        engine.add_vehicle(v)

    print(f"\n站点数: {len(stops)}")
    print(f"车辆数: {len(vehicles)}")
    print(f"仿真时长: {sim_config.sim_end_time}s")
    print(f"订单到达率: {sim_config.order_arrival_rate}单/分钟")
    print(f"派单间隔: {sim_config.dispatch_batch_interval}s")

    stats = engine.run(verbose=True)
    return stats


if __name__ == '__main__':
    main()
