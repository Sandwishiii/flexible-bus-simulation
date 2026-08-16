"""
仿真运行路由
"""
import math
import uuid
import threading
from fastapi import APIRouter, HTTPException
from web.models import SimulateRequest, SimulateResponse, MetricsReportResponse, TrajectoryResponse, SimProgressResponse
from web.routers.upload import get_session_data

router = APIRouter(prefix="/api", tags=["simulation"])


def _haversine(lng1, lat1, lng2, lat2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


_results_cache = {}
_progress_tracker = {}


@router.post("/simulate")
async def run_simulation(req: SimulateRequest):
    session = get_session_data()
    if not session.get("od_content"):
        raise HTTPException(status_code=400, detail="请先上传 OD 数据")
    if not session.get("station_content"):
        raise HTTPException(status_code=400, detail="请先上传站点数据")
    run_id = str(uuid.uuid4())[:8]
    _progress_tracker[run_id] = {"status": "running", "progress": 0.0, "message": "正在初始化仿真...", "result": None}
    thread = threading.Thread(target=_run_simulation_task, args=(run_id, req, dict(session)), daemon=True)
    thread.start()
    return {"run_id": run_id, "status": "running", "message": "仿真已启动"}


@router.get("/simulate/progress/{run_id}", response_model=SimProgressResponse)
async def get_progress(run_id: str):
    if run_id not in _progress_tracker:
        raise HTTPException(status_code=404, detail="未找到仿真任务")
    info = _progress_tracker[run_id]
    resp = SimProgressResponse(status=info["status"], progress=info["progress"], message=info["message"], run_id=run_id)
    if info["status"] == "completed" and info.get("result"):
        resp.metrics = MetricsReportResponse(**info["result"]["metrics"])
        _results_cache[run_id] = info["result"]
    return resp


def _run_simulation_task(run_id, req, session):
    try:
        tracker = _progress_tracker[run_id]
        from data.od_loader import ODLoader
        from data.station_loader import StationLoader
        from core.order import Order
        from core.vehicle import Vehicle
        from simulation.engine import SimEngine
        from config.settings import SimConfig, StopStrategy
        tracker["progress"] = 5
        tracker["message"] = "加载数据中..."
        od_loader = ODLoader()
        od_loader.load_from_string(session["od_content"])
        station_loader = StationLoader()
        if (session.get("station_content") or "").strip().startswith("--") or "INSERT" in (session.get("station_content") or ""):
            station_loader.load_sql_string(session["station_content"])
        else:
            station_loader.load_csv_string(session["station_content"])
        stops = station_loader.get_stops()
        if not stops:
            raise ValueError("站点数据为空")
        if session.get("region_wkt"):
            from data.region import parse_wkt_polygon
            polygon = parse_wkt_polygon(session["region_wkt"])
            od_loader.filter_by_region(polygon)
        tracker["progress"] = 10
        tracker["message"] = "展开订单中..."
        p = req.params
        od_p = req.od_expand
        peak_hours = []
        if od_p.time_distribution.value == "peak_weighted":
            peak_hours = [(od_p.peak_start_hour * 3600, od_p.peak_end_hour * 3600)]
        order_requests = od_loader.expand_orders(sim_start=od_p.sim_start_hour * 3600, sim_end=od_p.sim_end_hour * 3600, time_distribution=od_p.time_distribution.value, peak_hours=peak_hours, peak_weight=od_p.peak_weight, max_orders=od_p.max_orders)
        orders = []
        for i, oreq in enumerate(order_requests):
            origin_stop = min(stops, key=lambda s: _haversine(oreq.origin_lng, oreq.origin_lat, s.lng, s.lat))
            dest_stop = min(stops, key=lambda s: _haversine(oreq.dest_lng, oreq.dest_lat, s.lng, s.lat))
            if origin_stop.stop_id == dest_stop.stop_id:
                dest_stop = min([s for s in stops if s.stop_id != origin_stop.stop_id], key=lambda s: _haversine(oreq.dest_lng, oreq.dest_lat, s.lng, s.lat), default=dest_stop)
            order = Order(origin_lng=origin_stop.lng, origin_lat=origin_stop.lat, origin_stop_id=origin_stop.stop_id, origin_stop_name=origin_stop.name, dest_lng=dest_stop.lng, dest_lat=dest_stop.lat, dest_stop_id=dest_stop.stop_id, dest_stop_name=dest_stop.name, request_time=oreq.request_time, passenger_count=oreq.passenger_count)
            orders.append(order)
        if not orders:
            raise ValueError("展开后订单数为 0")
        tracker["progress"] = 15
        strategy_map = {"idle": StopStrategy.IDLE_AT_LOCATION, "cruise": StopStrategy.CRUISE_TO_HOTSPOT, "depot": StopStrategy.RETURN_TO_DEPOT}
        config = SimConfig(sim_start_time=int(od_p.sim_start_hour * 3600), sim_end_time=int(od_p.sim_end_hour * 3600), base_hour=int(od_p.sim_start_hour), dispatch_batch_interval=p.dispatch_interval, max_pickup_distance=p.max_pickup_distance, max_direction_angle=p.max_direction_angle, order_timeout_threshold=p.order_timeout, vehicle_speed=p.vehicle_speed, vehicle_capacity=p.vehicle_capacity, cost_per_km=p.cost_per_km, stop_strategy=strategy_map.get(p.stop_strategy.value, StopStrategy.IDLE_AT_LOCATION))
        engine = SimEngine(config=config)
        for stop in stops:
            engine.add_stop(stop)
        if req.vehicles:
            for vp in req.vehicles:
                vehicle = Vehicle(vehicle_id=vp.vehicle_id or f"V{len(engine.vehicles)+1:03d}", name=vp.name or f"云公交{len(engine.vehicles)+1}号", lng=vp.lng, lat=vp.lat, capacity=p.vehicle_capacity, service_start_time=config.sim_start_time, service_end_time=config.sim_end_time)
                engine.add_vehicle(vehicle)
            remaining = p.vehicle_count - len(req.vehicles)
            for i in range(remaining):
                stop_idx = (len(req.vehicles) + i) % len(stops)
                stop = stops[stop_idx]
                vehicle = Vehicle(vehicle_id=f"V{len(engine.vehicles)+1:03d}", name=f"云公交{len(engine.vehicles)+1}号", lng=stop.lng, lat=stop.lat, capacity=p.vehicle_capacity, service_start_time=config.sim_start_time, service_end_time=config.sim_end_time)
                engine.add_vehicle(vehicle)
        else:
            for i in range(p.vehicle_count):
                stop = stops[i % len(stops)]
                vehicle = Vehicle(vehicle_id=f"V{i+1:03d}", name=f"云公交{i+1}号", lng=stop.lng, lat=stop.lat, capacity=p.vehicle_capacity, service_start_time=config.sim_start_time, service_end_time=config.sim_end_time)
                engine.add_vehicle(vehicle)
        engine.set_od_orders(orders)
        engine.set_trajectory_interval(p.trajectory_interval)
        tracker["progress"] = 20
        if p.distance_mode == "navigation":
            from utils.distance_matrix import DistanceMatrix
            dm = DistanceMatrix(stops, vehicle_speed=p.vehicle_speed)
            dm.build(mode="navigation")
            engine.set_distance_matrix(dm)
        tracker["progress"] = 25
        sim_duration = config.sim_end_time - config.sim_start_time
        def progress_cb(current_time):
            pct = 25 + 65 * min(current_time / max(sim_duration, 1), 1.0)
            tracker["progress"] = pct
            hour = int(current_time // 3600)
            minute = int((current_time % 3600) // 60)
            tracker["message"] = f"仿真运行中... 模拟时间 {hour:02d}:{minute:02d}"
        engine.set_progress_callback(progress_cb)
        stats = engine.run(verbose=False)
        tracker["progress"] = 92
        report = engine.metrics_report
        trajectories = engine.get_trajectories_json()
        result = {"metrics": report.to_dict(), "trajectories": trajectories, "params": req.params.dict(), "orders": [{"order_id": o.order_id, "status": o.status.name, "origin_lng": o.origin_lng, "origin_lat": o.origin_lat, "dest_lng": o.dest_lng, "dest_lat": o.dest_lat, "wait_time": o.wait_time, "ride_distance": o.ride_distance, "assigned_vehicle_id": o.assigned_vehicle_id} for o in engine.orders]}
        tracker["result"] = result
        tracker["progress"] = 100
        tracker["status"] = "completed"
        tracker["message"] = f"仿真完成: {report.total_orders} 订单, {report.completed_orders} 完成, 完单率 {report.completion_rate:.1f}%"
    except Exception as e:
        tracker["status"] = "failed"
        tracker["message"] = f"仿真失败: {str(e)}"
        tracker["progress"] = 0


@router.get("/results/{run_id}")
async def get_results(run_id: str):
    if run_id not in _results_cache:
        raise HTTPException(status_code=404, detail=f"未找到仿真结果: {run_id}")
    return _results_cache[run_id]["metrics"]


@router.get("/trajectory/{run_id}", response_model=TrajectoryResponse)
async def get_trajectory(run_id: str):
    if run_id not in _results_cache:
        raise HTTPException(status_code=404, detail=f"未找到仿真结果: {run_id}")
    return TrajectoryResponse(run_id=run_id, trajectories=_results_cache[run_id]["trajectories"])


@router.get("/orders/{run_id}")
async def get_orders(run_id: str):
    if run_id not in _results_cache:
        raise HTTPException(status_code=404, detail=f"未找到仿真结果: {run_id}")
    return _results_cache[run_id]["orders"]


@router.get("/export/{run_id}/csv")
async def export_csv(run_id: str):
    if run_id not in _results_cache:
        raise HTTPException(status_code=404, detail=f"未找到仿真结果: {run_id}")
    from fastapi.responses import Response
    from simulation.metrics import MetricsReport
    cached = _results_cache[run_id]
    metrics_data = cached["metrics"]
    report = MetricsReport(**metrics_data)
    param_labels = {'sim_start_hour': '仿真起始小时', 'sim_duration_hours': '仿真时长(小时)', 'dispatch_interval': '派单周期(秒)', 'max_pickup_distance': '最大接驾距离(米)', 'max_direction_angle': '方向夹角阈值(度)', 'order_timeout': '订单超时阈值(秒)', 'vehicle_count': '车辆数', 'vehicle_speed': '车速(km/h)', 'vehicle_capacity': '车辆容量(座位)', 'cost_per_km': '单公里成本(元)', 'stop_strategy': '停靠策略', 'trajectory_interval': '轨迹记录间隔(秒)', 'distance_mode': '距离模式'}
    lines = ['# 仿真参数']
    params = cached.get('params', {})
    for key, value in params.items():
        label = param_labels.get(key, key)
        lines.append(f'{label},{value}')
    lines.append('')
    lines.append('# 指标报告')
    lines.append(report.to_csv())
    full_csv = '\n'.join(lines)
    return Response(content=full_csv, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=metrics_{run_id}.csv"})
