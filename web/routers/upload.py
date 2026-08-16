"""
上传接口路由
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from web.models import ODUploadResponse, StationUploadResponse, RegionUploadResponse

router = APIRouter(prefix="/api/upload", tags=["upload"])

_session_data = {"od_content": None, "station_content": None, "region_wkt": None}


def get_session_data():
    return _session_data


@router.post("/od", response_model=ODUploadResponse)
async def upload_od(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8-sig")
        from data.od_loader import ODLoader
        loader = ODLoader()
        n = loader.load_from_string(text)
        if n == 0:
            raise HTTPException(status_code=400, detail="未解析到有效 OD 记录")
        _session_data["od_content"] = text
        summary = loader.get_summary()
        records = loader.get_records()
        truncated = len(records) > 1000
        display_records = records[:1000] if truncated else records
        od_records = [{"o_x": r.origin_lng, "o_y": r.origin_lat, "d_x": r.dest_lng, "d_y": r.dest_lat, "total_uv": r.total_demand} for r in display_records]
        return ODUploadResponse(total_records=summary["total_records"], total_demand=summary["total_demand"], avg_demand=summary["avg_demand"], format=summary["format"], o_lng_range=list(summary.get("o_lng_range", [0, 0])), o_lat_range=list(summary.get("o_lat_range", [0, 0])), d_lng_range=list(summary.get("d_lng_range", [0, 0])), d_lat_range=list(summary.get("d_lat_range", [0, 0])), od_records=od_records, truncated=truncated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/stations", response_model=StationUploadResponse)
async def upload_stations(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8-sig")
        from data.station_loader import StationLoader
        loader = StationLoader()
        filename = file.filename or ""
        if filename.endswith(".sql"):
            n = loader.load_sql_string(text)
        else:
            n = loader.load_csv_string(text)
        if n == 0:
            raise HTTPException(status_code=400, detail="未解析到有效站点")
        _session_data["station_content"] = text
        summary = loader.get_summary()
        stops_data = [{"id": s.stop_id, "name": s.name, "lng": s.lng, "lat": s.lat} for s in loader.get_stops()]
        return StationUploadResponse(total_stops=summary["total_stops"], total_routes=summary.get("total_routes", 0), routes=summary.get("routes", []), stops=stops_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/region", response_model=RegionUploadResponse)
async def upload_region(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8-sig").strip()
        from data.region import parse_wkt_polygon, polygon_bbox
        vertices = parse_wkt_polygon(text)
        bbox = polygon_bbox(vertices)
        _session_data["region_wkt"] = text
        return RegionUploadResponse(vertex_count=len(vertices), bbox=list(bbox), vertices=[list(v) for v in vertices])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/region-text", response_model=RegionUploadResponse)
async def upload_region_text(wkt: str = Body(..., embed=True)):
    try:
        text = wkt.strip()
        if not text:
            raise HTTPException(status_code=400, detail="WKT 文本为空")
        from data.region import parse_wkt_polygon, polygon_bbox
        vertices = parse_wkt_polygon(text)
        bbox = polygon_bbox(vertices)
        _session_data["region_wkt"] = text
        return RegionUploadResponse(vertex_count=len(vertices), bbox=list(bbox), vertices=[list(v) for v in vertices])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
