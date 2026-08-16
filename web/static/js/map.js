/**
 * 高德地图交互模块
 * 管理地图实例、站点标记、OD线、区域边界、车辆标记
 */

let map = null;
let stationMarkers = [];
let odLines = [];
let regionPolygon = null;
let vehicleMarkers = {};
let odVisible = true;

const VEHICLE_COLORS = [
    '#ea4335', '#34a853', '#f9ab00', '#4285f4', '#ff6d01',
    '#46bdc6', '#7b61ff', '#e8710a', '#1a73e8', '#d93025',
];

function initMap() {
    map = new AMap.Map('map', {
        zoom: 12,
        center: [106.78, 26.54],
        mapStyle: 'amap://styles/light',
    });
}

function showStations(stops) {
    clearStations();
    stops.forEach(function(stop) {
        var marker = new AMap.Marker({
            position: [stop.lng, stop.lat],
            title: stop.name,
            content: '<div style="width:10px;height:10px;background:#1a73e8;border-radius:50%;border:2px solid white;"></div>',
            offset: new AMap.Pixel(-5, -5),
        });
        marker.on('click', function() {
            var info = new AMap.InfoWindow({
                content: '<div style="padding:4px;font-size:12px;"><b>' + stop.name + '</b><br>坐标: ' + stop.lng.toFixed(4) + ', ' + stop.lat.toFixed(4) + '</div>',
                offset: new AMap.Pixel(0, -10),
            });
            info.open(map, marker.getPosition());
        });
        marker.setMap(map);
        stationMarkers.push(marker);
    });
    if (stops.length > 0) {
        map.setFitView(stationMarkers, false, [50, 50, 50, 50]);
    }
}

function clearStations() {
    stationMarkers.forEach(function(m) { m.setMap(null); });
    stationMarkers = [];
}

function showODLines(odData) {
    clearODLines();
    if (!odData || odData.length === 0) return;
    var minUV = Infinity, maxUV = -Infinity;
    odData.forEach(function(od) {
        var uv = od.total_uv || 1;
        if (uv < minUV) minUV = uv;
        if (uv > maxUV) maxUV = uv;
    });
    var range = maxUV - minUV || 1;
    odData.forEach(function(od) {
        var uv = od.total_uv || 1;
        var t = (uv - minUV) / range;
        var r, g, b;
        if (t < 0.5) {
            var s = t * 2;
            r = Math.round(0 + 255 * s);
            g = Math.round(180 + 20 * s);
            b = 0;
        } else {
            var s = (t - 0.5) * 2;
            r = Math.round(255 - 25 * s);
            g = Math.round(200 - 150 * s);
            b = Math.round(0 + 30 * s);
        }
        var color = 'rgb(' + r + ',' + g + ',' + b + ')';
        var weight = 2 + 6 * t;
        var opacity = 0.35 + 0.3 * t;
        var line = new AMap.Polyline({
            path: [[od.o_x, od.o_y], [od.d_x, od.d_y]],
            strokeColor: color,
            strokeOpacity: opacity,
            strokeWeight: weight,
            map: map,
        });
        odLines.push(line);
    });
}

function clearODLines() {
    odLines.forEach(function(l) { l.setMap(null); });
    odLines = [];
}

function toggleODLines() {
    odVisible = !odVisible;
    odLines.forEach(function(l) { l.setMap(odVisible ? map : null); });
}

function showRegion(vertices) {
    clearRegion();
    if (!vertices || vertices.length < 3) return;
    var path = vertices.map(function(v) { return [v[0], v[1]]; });
    regionPolygon = new AMap.Polygon({
        path: path,
        fillColor: '#1a73e8',
        fillOpacity: 0.1,
        strokeColor: '#1a73e8',
        strokeWeight: 2,
        strokeOpacity: 0.6,
        bubble: true,
        map: map,
    });
    map.setFitView([regionPolygon], false, [50, 50, 50, 50]);
}

function clearRegion() {
    if (regionPolygon) { regionPolygon.setMap(null); regionPolygon = null; }
}

function showVehicleMarkers(trajectories) {
    clearVehicleMarkers();
    var idx = 0;
    for (var vid in trajectories) {
        var traj = trajectories[vid];
        if (!traj || traj.length === 0) continue;
        var busImgIdx = (idx % 10) + 1;
        var busImgNum = busImgIdx < 10 ? '0' + busImgIdx : '' + busImgIdx;
        var busImgSrc = '/static/assets/bus_' + busImgNum + '.png';
        var vehicleLabel = 'V' + (idx + 1);
        var statusColor = getStatusColor(traj[0][3] || 'IDLE');
        var markerContent = '<div class="vehicle-marker-wrap" data-vid="' + vid + '" style="position:relative;width:32px;height:32px;background:transparent;border:none;padding:0;margin:0;">' +
                     '<div class="vehicle-dot" data-vid="' + vid + '" style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:14px;height:14px;background:' + statusColor + ';border-radius:50%;border:2px solid white;z-index:1;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.4);"></div>' +
                     '<img src="' + busImgSrc + '" style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:32px;height:32px;display:block;background:transparent;border:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,0.4));z-index:2;pointer-events:none;" />' +
                     '<div style="position:absolute;top:-16px;left:50%;transform:translateX(-50%);background:#333;color:white;padding:1px 4px;border-radius:3px;font-size:10px;white-space:nowrap;z-index:3;">' + vehicleLabel + '</div>' +
                     '</div>';
        var marker = new AMap.Marker({
            position: [traj[0][1], traj[0][2]],
            content: markerContent,
            offset: new AMap.Pixel(-16, -16),
            title: vid,
            map: map,
        });
        (function(vehicleId) {
            setTimeout(function() {
                var dotEl = document.querySelector('.vehicle-dot[data-vid="' + vehicleId + '"]');
                if (dotEl) {
                    dotEl.addEventListener('click', function(e) {
                        e.stopPropagation();
                        showVehicleInfo(vehicleId);
                    });
                }
            }, 200);
        })(vid);
        var color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
        var fullPath = [];
        for (var k = 0; k < traj.length; k++) {
            fullPath.push([traj[k][1], traj[k][2]]);
        }
        var trailLine = new AMap.Polyline({
            path: fullPath,
            strokeColor: color,
            strokeWeight: 3,
            strokeOpacity: 0.5,
            strokeStyle: 'dashed',
            map: map,
        });
        var traveledLine = new AMap.Polyline({
            path: [[traj[0][1], traj[0][2]]],
            strokeColor: color,
            strokeWeight: 4,
            strokeOpacity: 0.9,
            strokeStyle: 'solid',
            map: map,
        });
        vehicleMarkers[vid] = {
            marker: marker,
            color: color,
            trajectory: traj,
            trailLine: trailLine,
            traveledLine: traveledLine,
            trailPoints: [[traj[0][1], traj[0][2]]],
            busImgSrc: busImgSrc,
            vehicleLabel: vehicleLabel,
        };
        idx++;
    }
    updateVehicleFilter();
}

function clearVehicleMarkers() {
    for (var vid in vehicleMarkers) {
        vehicleMarkers[vid].marker.setMap(null);
        if (vehicleMarkers[vid].trailLine) vehicleMarkers[vid].trailLine.setMap(null);
        if (vehicleMarkers[vid].traveledLine) vehicleMarkers[vid].traveledLine.setMap(null);
    }
    vehicleMarkers = {};
}

var _diagLogged = false;
function updateVehiclePositions(timePoint) {
    for (var vid in vehicleMarkers) {
        var vm = vehicleMarkers[vid];
        var traj = vm.trajectory;
        var pos = findPositionAtTime(traj, timePoint);
        if (pos) {
            var newPos = [pos[1], pos[2]];
            vm.marker.setPosition(newPos);
            var statusColor = getStatusColor(pos[3]);
            var passengers = pos[4] || 0;
            var orders = pos[5] || 0;
            var distance = pos[6] || 0;
            vm.currentStats = {
                status: pos[3],
                passengers: passengers,
                orders: orders,
                distance: distance,
                time: pos[0],
            };
            var dotEl = document.querySelector('.vehicle-dot[data-vid="' + vid + '"]');
            if (dotEl) dotEl.style.background = statusColor;
            var lastPoint = vm.trailPoints[vm.trailPoints.length - 1];
            if (newPos[0] !== lastPoint[0] || newPos[1] !== lastPoint[1]) {
                vm.trailPoints.push(newPos);
                if (vm.traveledLine) vm.traveledLine.setPath(vm.trailPoints);
            }
        }
    }
    _diagLogged = true;
}

function findPositionAtTime(trajectory, time) {
    if (!trajectory || trajectory.length === 0) return null;
    if (time < trajectory[0][0]) return trajectory[0];
    for (var i = 0; i < trajectory.length - 1; i++) {
        var p1 = trajectory[i];
        var p2 = trajectory[i + 1];
        if (time >= p1[0] && time < p2[0]) {
            var dt = p2[0] - p1[0];
            var progress = dt > 0 ? (time - p1[0]) / dt : 0;
            var lng = p1[1] + (p2[1] - p1[1]) * progress;
            var lat = p1[2] + (p2[2] - p1[2]) * progress;
            return [p1[0], lng, lat, p1[3], p1[4] || 0, p1[5] || 0, p1[6] || 0];
        }
    }
    return trajectory[trajectory.length - 1];
}

function getStatusColor(status) {
    switch (status) {
        case 'IDLE': return '#999';
        case 'ENROUTE_PICKUP': return '#f9ab00';
        case 'IN_SERVICE': return '#34a853';
        case 'CRUISING': return '#4285f4';
        case 'AT_STOP': return '#46bdc6';
        default: return '#999';
    }
}

function getStatusText(status) {
    switch (status) {
        case 'IDLE': return '空闲待命';
        case 'ENROUTE_PICKUP': return '前往接驾';
        case 'IN_SERVICE': return '载客行驶';
        case 'CRUISING': return '空载巡游';
        case 'AT_STOP': return '站点停靠';
        case 'OFF_DUTY': return '收班';
        case 'FINISHED': return '已完成';
        default: return status || '未知';
    }
}

function showVehicleInfo(vid) {
    var vm = vehicleMarkers[vid];
    if (!vm) return;
    var stats = vm.currentStats || {};
    var statusText = getStatusText(stats.status);
    var statusColor = getStatusColor(stats.status);
    var timeStr = '';
    if (stats.time !== undefined) {
        var hours = Math.floor(stats.time / 3600);
        var minutes = Math.floor((stats.time % 3600) / 60);
        var seconds = Math.floor(stats.time % 60);
        timeStr = hours + ':' + String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
    }
    var distStr = '';
    if (stats.distance !== undefined) {
        if (stats.distance >= 1000) distStr = (stats.distance / 1000).toFixed(1) + ' km';
        else distStr = Math.round(stats.distance) + ' m';
    }
    var content = '<div style="padding:8px 12px;min-width:160px;font-size:12px;line-height:1.8;">' +
        '<div style="font-weight:bold;font-size:13px;margin-bottom:4px;border-bottom:1px solid #eee;padding-bottom:4px;">' +
        '<span style="color:' + statusColor + ';">●</span> ' + vm.vehicleLabel + ' - ' + statusText +
        '</div>' +
        '<div>在车乘客: <b>' + (stats.passengers || 0) + '</b> 人</div>' +
        '<div>已完成订单: <b>' + (stats.orders || 0) + '</b> 单</div>' +
        '<div>运行里程: <b>' + distStr + '</b></div>' +
        (timeStr ? '<div style="color:#999;font-size:11px;margin-top:2px;">时刻: ' + timeStr + '</div>' : '') +
        '</div>';
    var infoWindow = new AMap.InfoWindow({
        content: content,
        offset: new AMap.Pixel(0, -20),
    });
    infoWindow.open(map, vm.marker.getPosition());
}

function updateVehicleFilter() {
    var container = document.getElementById('vehicle-filter');
    if (!container) return;
    var html = '<span style="font-size:11px;color:#666;margin-right:6px;">显示:</span>';
    html += '<label style="font-size:11px;cursor:pointer;margin-right:8px;"><input type="checkbox" id="filter-all" checked onchange="toggleAllVehicles(this.checked)"> 全部</label>';
    var idx = 0;
    for (var vid in vehicleMarkers) {
        var vm = vehicleMarkers[vid];
        html += '<label style="font-size:11px;cursor:pointer;margin-right:6px;">' +
                '<input type="checkbox" class="vehicle-filter-cb" data-vid="' + vid + '" checked onchange="toggleVehicle(\'' + vid + '\', this.checked)"> ' +
                vm.vehicleLabel + '</label>';
        idx++;
    }
    container.innerHTML = html;
}

function toggleAllVehicles(show) {
    var checkboxes = document.querySelectorAll('.vehicle-filter-cb');
    checkboxes.forEach(function(cb) {
        cb.checked = show;
        toggleVehicle(cb.dataset.vid, show);
    });
}

function toggleVehicle(vid, show) {
    var vm = vehicleMarkers[vid];
    if (!vm) return;
    if (show) {
        vm.marker.setMap(map);
        if (vm.trailLine) vm.trailLine.setMap(map);
        if (vm.traveledLine) vm.traveledLine.setMap(map);
    } else {
        vm.marker.setMap(null);
        if (vm.trailLine) vm.trailLine.setMap(null);
        if (vm.traveledLine) vm.traveledLine.setMap(null);
    }
    var checkboxes = document.querySelectorAll('.vehicle-filter-cb');
    var allChecked = Array.from(checkboxes).every(function(cb) { return cb.checked; });
    var allCheckbox = document.getElementById('filter-all');
    if (allCheckbox) allCheckbox.checked = allChecked;
}