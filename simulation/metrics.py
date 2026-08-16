"""
仿真指标报告生成
"""
import json
import csv
import io
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from core.vehicle import Vehicle
from core.order import Order, OrderStatus


@dataclass
class MetricsReport:
    total_orders: int = 0
    dispatched_orders: int = 0
    completed_orders: int = 0
    timeout_orders: int = 0
    cancelled_orders: int = 0
    completion_rate: float = 0.0
    timeout_rate: float = 0.0
    avg_wait_time: float = 0.0
    avg_ride_time: float = 0.0
    avg_ride_distance: float = 0.0
    avg_pickup_distance: float = 0.0
    max_concurrent_orders: int = 0
    avg_concurrent_orders: float = 0.0
    total_vehicle_distance: float = 0.0
    total_order_distance: float = 0.0
    total_empty_distance: float = 0.0
    empty_rate: float = 0.0
    orders_per_100km: float = 0.0
    carpool_intensity: float = 0.0
    cost_per_km: float = 14.0
    total_cost: float = 0.0
    cost_per_passenger: float = 0.0
    sim_duration: float = 0.0
    vehicle_count: int = 0
    stop_count: int = 0

    def to_dict(self):
        return asdict(self)

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_text(self):
        lines = []
        lines.append("=" * 55)
        lines.append("         灵活公交仿真 - 指标报告")
        lines.append("=" * 55)
        lines.append(f"\n--- 基础统计 ---")
        lines.append(f"  总订单数:         {self.total_orders}")
        lines.append(f"  已派单数:         {self.dispatched_orders}")
        lines.append(f"  已完成数:         {self.completed_orders}")
        lines.append(f"  超时未应答:       {self.timeout_orders}")
        lines.append(f"\n--- 服务体验 ---")
        lines.append(f"  完单率:           {self.completion_rate:.1f}%")
        lines.append(f"  超时率:           {self.timeout_rate:.1f}%")
        lines.append(f"  平均候车时间:     {self.avg_wait_time:.0f}s ({self.avg_wait_time/60:.1f}min)")
        lines.append(f"  平均在车时间:     {self.avg_ride_time:.0f}s ({self.avg_ride_time/60:.1f}min)")
        lines.append(f"  平均乘车距离:     {self.avg_ride_distance/1000:.1f}km")
        lines.append(f"  平均接驾距离:     {self.avg_pickup_distance/1000:.2f}km")
        lines.append(f"\n--- 运营效率 ---")
        lines.append(f"  车辆总里程:       {self.total_vehicle_distance/1000:.1f}km")
        lines.append(f"  空驶率:           {self.empty_rate:.1f}%")
        lines.append(f"\n--- 成本指标 ---")
        lines.append(f"  总运营成本:       {self.total_cost:.0f}元")
        lines.append(f"  单人运送成本:     {self.cost_per_passenger:.1f}元")
        lines.append("\n" + "=" * 55)
        return "\n".join(lines)

    def to_csv(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["指标名称", "指标值", "单位"])
        d = self.to_dict()
        unit_map = {"completion_rate": "%", "timeout_rate": "%", "empty_rate": "%", "avg_wait_time": "秒", "avg_ride_time": "秒", "avg_ride_distance": "米", "avg_pickup_distance": "米", "total_vehicle_distance": "米", "total_order_distance": "米", "total_empty_distance": "米", "total_cost": "元", "cost_per_passenger": "元", "sim_duration": "秒"}
        name_map = {"total_orders": "总订单数", "dispatched_orders": "已派单数", "completed_orders": "已完成数", "timeout_orders": "超时未应答", "cancelled_orders": "取消订单数", "completion_rate": "完单率", "timeout_rate": "超时率", "avg_wait_time": "平均候车时间", "avg_ride_time": "平均在车时间", "avg_ride_distance": "平均乘车距离", "avg_pickup_distance": "平均接驾距离", "max_concurrent_orders": "最高同时在车订单数", "total_vehicle_distance": "车辆总里程", "total_order_distance": "订单里程", "total_empty_distance": "空驶里程", "empty_rate": "空驶率", "orders_per_100km": "百公里订单量", "carpool_intensity": "合乘强度", "cost_per_km": "单公里成本", "total_cost": "总运营成本", "cost_per_passenger": "单人运送成本", "sim_duration": "仿真时长", "vehicle_count": "车辆数", "stop_count": "站点数"}
        for key, value in d.items():
            name = name_map.get(key, key)
            unit = unit_map.get(key, "")
            writer.writerow([name, value, unit])
        return output.getvalue()


def compute_metrics(vehicles, orders, stats, sim_duration=0.0, cost_per_km=14.0):
    report = MetricsReport()
    report.total_orders = stats.get("total_orders", 0)
    report.dispatched_orders = stats.get("dispatched_orders", 0)
    report.completed_orders = stats.get("completed_orders", 0)
    report.timeout_orders = stats.get("timeout_orders", 0)
    report.cancelled_orders = stats.get("cancelled_orders", 0)
    if report.total_orders > 0:
        report.completion_rate = report.completed_orders / report.total_orders * 100
        report.timeout_rate = report.timeout_orders / report.total_orders * 100
    completed = [o for o in orders if o.status == OrderStatus.COMPLETED]
    if completed:
        report.avg_wait_time = sum(o.wait_time for o in completed) / len(completed)
        report.avg_ride_time = sum(o.ride_duration for o in completed) / len(completed)
        report.avg_ride_distance = sum(o.ride_distance for o in completed) / len(completed)
        report.avg_pickup_distance = sum(o.pickup_distance for o in completed) / len(completed)
    report.max_concurrent_orders = stats.get("max_concurrent_orders", 0)
    report.total_vehicle_distance = sum(v.total_distance for v in vehicles)
    report.total_order_distance = sum(v.order_distance for v in vehicles)
    report.total_empty_distance = sum(v.empty_distance for v in vehicles)
    if report.total_vehicle_distance > 0:
        report.empty_rate = report.total_empty_distance / report.total_vehicle_distance * 100
        report.orders_per_100km = report.completed_orders / (report.total_vehicle_distance / 1000) * 100
    if report.total_order_distance > 0:
        report.carpool_intensity = report.completed_orders / (report.total_order_distance / 1000)
    report.cost_per_km = cost_per_km
    report.total_cost = (report.total_vehicle_distance / 1000) * cost_per_km
    if report.completed_orders > 0:
        report.cost_per_passenger = report.total_cost / report.completed_orders
    report.sim_duration = sim_duration
    report.vehicle_count = len(vehicles)
    return report
