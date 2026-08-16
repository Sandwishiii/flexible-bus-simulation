/**
 * 主逻辑模块
 * 处理文件上传、参数收集、仿真运行、结果显示
 */

var currentRunId = null;
var uploadedStations = null;
var mapPickMode = false;
var vehicleRowCounter = 0;
var dataLoaded = { od: false, stations: false, region: false };

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    setupFileUploads();
    var count = parseInt(document.getElementById('p-vehicle-count').value) || 5;
    for (var i = 0; i < count; i++) {
        addVehicleRow();
    }
    document.getElementById('p-vehicle-count').addEventListener('change', function() {
        var target = parseInt(this.value) || 5;
        var current = document.querySelectorAll('.vehicle-row').length;
        while (current < target) { addVehicleRow(); current++; }
        while (current > target) {
            var rows = document.querySelectorAll('.vehicle-row');
            if (rows.length > 0) rows[rows.length - 1].remove();
            current--;
        }
    });
});

function setupFileUploads() {
    document.getElementById('od-file').addEventListener('change', function(e) {
        uploadFile('/api/upload/od', e.target.files[0], 'od-status', function(data) {
            var msg = '已加载: ' + data.total_records + ' 条OD, 总需求 ' + data.total_demand;
            if (data.truncated) msg += ' (显示前1000条)';
            setStatus('od-status', msg, 'success');
            if (data.od_records && data.od_records.length > 0) {
                showODLines(data.od_records);
            }
        });
    });

    document.getElementById('station-file').addEventListener('change', function(e) {
        uploadFile('/api/upload/stations', e.target.files[0], 'station-status', function(data) {
            uploadedStations = data.stops;
            setStatus('station-status',
                '已加载: ' + data.total_stops + ' 个站点 (' + data.routes.join(', ') + ')',
                'success');
            showStations(data.stops);
        });
    });
}

function uploadFile(url, file, statusId, onSuccess) {
    if (!file) return;
    setStatus(statusId, '上传中...', '');
    var formData = new FormData();
    formData.append('file', file);
    fetch(url, { method: 'POST', body: formData })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.detail) {
            setStatus(statusId, '错误: ' + data.detail, 'error');
            return;
        }
        if (url.indexOf('/upload/od') >= 0) dataLoaded.od = true;
        if (url.indexOf('/upload/stations') >= 0) dataLoaded.stations = true;
        onSuccess(data);
    })
    .catch(function(err) {
        setStatus(statusId, '上传失败: ' + err.message, 'error');
    });
}

function toggleFormat(id) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle('hidden');
}

function downloadSample(type) {
    var content = '', filename = '';
    if (type === 'od') {
        content = 'o_x,o_y,d_x,d_y,total_uv,duration,distance\n' +
            '106.8056,26.5378,106.7805,26.5468,1523,1800,5200\n' +
            '106.7995,26.5450,106.7034,26.5495,892,1200,8400\n' +
            '106.7895,26.5351,106.7235,26.5828,654,900,6100\n' +
            '106.7705,26.5459,106.7385,26.5495,1102,1500,3200\n' +
            '106.8056,26.5378,106.6744,26.6197,445,2100,12500';
        filename = 'od_sample.csv';
    } else if (type === 'station') {
        content = 'name,lng,lat\n' +
            '双龙实验小学,106.7614,26.5066\n' +
            '小碧营盘,106.7627,26.5095\n' +
            '云峰路口,106.7634,26.5186\n' +
            '龙水路中,106.7712,26.5298\n' +
            '双龙南站,106.7805,26.5468';
        filename = 'station_sample.csv';
    }
    var blob = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function runSimulation() {
    var missing = [];
    if (!dataLoaded.od) missing.push('OD 数据');
    if (!dataLoaded.stations) missing.push('站点数据');
    if (missing.length > 0) {
        alert('请先加载以下数据：\n' + missing.join('、'));
        return;
    }
    var vehicleCount = parseInt(document.getElementById('p-vehicle-count').value);
    var filledVehicles = collectVehicles();
    if (filledVehicles.length < vehicleCount) {
        var missingCount = vehicleCount - filledVehicles.length;
        if (!confirm('有 ' + missingCount + ' 辆车未设置初始位置，将自动分配到不同站点。是否继续？')) {
            return;
        }
    }
    var btn = document.getElementById('btn-run');
    btn.disabled = true;
    btn.textContent = '仿真运行中...';
    var progressWrap = document.getElementById('progress-wrap');
    var progressBar = document.getElementById('progress-bar');
    var progressText = document.getElementById('progress-text');
    progressWrap.classList.remove('hidden');
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
    setStatus('run-status', '正在初始化仿真...', '');
    var peakStart = parseFloat(document.getElementById('p-peak-start').value);
    var peakEnd = parseFloat(document.getElementById('p-peak-end').value);
    var startHour = peakStart;
    var duration = peakEnd - peakStart;
    var requestBody = {
        params: {
            sim_start_hour: startHour,
            sim_duration_hours: duration,
            dispatch_interval: parseFloat(document.getElementById('p-dispatch').value),
            max_pickup_distance: parseFloat(document.getElementById('p-pickup').value),
            max_direction_angle: parseFloat(document.getElementById('p-angle').value),
            order_timeout: parseFloat(document.getElementById('p-timeout').value),
            vehicle_count: parseInt(document.getElementById('p-vehicle-count').value),
            vehicle_speed: parseFloat(document.getElementById('p-speed').value),
            vehicle_capacity: 20,
            cost_per_km: parseFloat(document.getElementById('p-cost').value),
            stop_strategy: document.getElementById('p-strategy').value,
            trajectory_interval: 10,
            distance_mode: document.getElementById('p-distance-mode').value,
        },
        od_expand: {
            time_distribution: document.getElementById('p-time-dist').value,
            peak_start_hour: peakStart,
            peak_end_hour: peakEnd,
            peak_weight: parseFloat(document.getElementById('p-peak-weight').value),
            max_orders: parseInt(document.getElementById('p-max-orders').value),
            sim_start_hour: startHour,
            sim_end_hour: startHour + duration,
        },
        vehicles: collectVehicles(),
    };
    fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.detail) {
            setStatus('run-status', '失败: ' + data.detail, 'error');
            btn.disabled = false;
            btn.textContent = '运行仿真';
            progressWrap.classList.add('hidden');
            return;
        }
        currentRunId = data.run_id;
        pollProgress(data.run_id, btn, progressWrap, progressBar, progressText, startHour, startHour + duration);
    })
    .catch(function(err) {
        btn.disabled = false;
        btn.textContent = '运行仿真';
        setStatus('run-status', '请求失败: ' + err.message, 'error');
        progressWrap.classList.add('hidden');
    });
}

function pollProgress(runId, btn, progressWrap, progressBar, progressText, simStart, simEnd) {
    var pollInterval = setInterval(function() {
        fetch('/api/simulate/progress/' + runId)
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            var pct = Math.round(data.progress || 0);
            progressBar.style.width = pct + '%';
            progressText.textContent = pct + '%';
            setStatus('run-status', data.message || '运行中...', '');
            if (data.status === 'completed') {
                clearInterval(pollInterval);
                progressBar.style.width = '100%';
                progressText.textContent = '100%';
                btn.disabled = false;
                btn.textContent = '运行仿真';
                setStatus('run-status', data.message, 'success');
                if (data.metrics) displayMetrics(data.metrics);
                document.getElementById('btn-export').disabled = false;
                loadTrajectoryData(runId, simStart, simEnd);
                setTimeout(function() { progressWrap.classList.add('hidden'); }, 3000);
            } else if (data.status === 'failed') {
                clearInterval(pollInterval);
                btn.disabled = false;
                btn.textContent = '运行仿真';
                setStatus('run-status', data.message, 'error');
                progressWrap.classList.add('hidden');
            }
        })
        .catch(function(err) { console.warn('轮询进度失败:', err); });
    }, 500);
}

function loadTrajectoryData(runId, simStart, simEnd) {
    fetch('/api/trajectory/' + runId)
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.trajectories) {
            loadTrajectory(data.trajectories, simStart * 3600, simEnd * 3600);
        }
    })
    .catch(function(err) { console.error('轨迹加载失败:', err); });
}

function displayMetrics(metrics) {
    var html = '';
    html += '<div class="metric-group">';
    html += '<div class="metric-group-title">基础统计</div>';
    html += metricRow('总订单数', metrics.total_orders);
    html += metricRow('已派单', metrics.dispatched_orders);
    html += metricRow('已完成', metrics.completed_orders);
    html += metricRow('超时未应答', metrics.timeout_orders);
    html += '</div>';
    html += '<div class="metric-group">';
    html += '<div class="metric-group-title">服务体验</div>';
    html += metricRow('完单率', metrics.completion_rate.toFixed(1) + '%', metrics.completion_rate > 70 ? 'good' : metrics.completion_rate > 50 ? 'warn' : 'bad');
    html += metricRow('超时率', metrics.timeout_rate.toFixed(1) + '%', metrics.timeout_rate < 20 ? 'good' : metrics.timeout_rate < 40 ? 'warn' : 'bad');
    html += metricRow('平均候车', formatTime(metrics.avg_wait_time));
    html += metricRow('平均在车', formatTime(metrics.avg_ride_time));
    html += metricRow('平均接驾', (metrics.avg_pickup_distance / 1000).toFixed(2) + ' km');
    html += metricRow('最高同时在车', metrics.max_concurrent_orders);
    html += '</div>';
    html += '<div class="metric-group">';
    html += '<div class="metric-group-title">运营效率</div>';
    html += metricRow('车辆总里程', (metrics.total_vehicle_distance / 1000).toFixed(1) + ' km');
    html += metricRow('空驶率', metrics.empty_rate.toFixed(1) + '%', metrics.empty_rate < 30 ? 'good' : metrics.empty_rate < 50 ? 'warn' : 'bad');
    html += metricRow('百公里订单', metrics.orders_per_100km.toFixed(1));
    html += metricRow('合乘强度', metrics.carpool_intensity.toFixed(2));
    html += '</div>';
    html += '<div class="metric-group">';
    html += '<div class="metric-group-title">成本</div>';
    html += metricRow('总成本', metrics.total_cost.toFixed(0) + ' 元');
    html += metricRow('单人成本', metrics.cost_per_passenger.toFixed(1) + ' 元');
    html += '</div>';
    document.getElementById('metrics-content').innerHTML = html;
}

function metricRow(label, value, cls) {
    var valueClass = cls ? ' class="metric-value ' + cls + '"' : ' class="metric-value"';
    return '<div class="metric-row"><span class="metric-label">' + label + '</span><span' + valueClass + '>' + value + '</span></div>';
}

function formatTime(seconds) {
    if (seconds < 60) return seconds.toFixed(0) + 's';
    return (seconds / 60).toFixed(1) + 'min';
}

function exportCSV() {
    if (!currentRunId) return;
    window.open('/api/export/' + currentRunId + '/csv', '_blank');
}

function setStatus(id, text, type) {
    var el = document.getElementById(id);
    el.textContent = text;
    el.className = 'status-text' + (type ? ' ' + type : '');
}

// ---- 车辆位置管理 ----
function addVehicleRow(lng, lat, marker) {
    vehicleRowCounter++;
    var list = document.getElementById('vehicle-list');
    var row = document.createElement('div');
    row.className = 'vehicle-row';
    row.dataset.idx = vehicleRowCounter;
    var html = '<span>V' + vehicleRowCounter + '</span>' +
        '<input type="number" step="0.0001" placeholder="经度" value="' + (lng || '') + '">' +
        '<input type="number" step="0.0001" placeholder="纬度" value="' + (lat || '') + '">';
    if (vehicleRowCounter > 1) {
        html += '<button class="btn-same" onclick="copyPrevVehicle(this)" title="与上一辆车相同">同上</button>';
    }
    html += '<button class="btn-remove" onclick="removeVehicleRow(this)" title="删除">x</button>';
    row.innerHTML = html;
    if (marker) row._mapMarker = marker;
    list.appendChild(row);
    updateVehicleCountInfo();
}

function copyPrevVehicle(btn) {
    var row = btn.parentElement;
    var prevRow = row.previousElementSibling;
    if (!prevRow || !prevRow.classList.contains('vehicle-row')) return;
    var prevInputs = prevRow.querySelectorAll('input');
    var curInputs = row.querySelectorAll('input');
    curInputs[0].value = prevInputs[0].value;
    curInputs[1].value = prevInputs[1].value;
}

function removeVehicleRow(btn) {
    var row = btn.parentElement;
    if (row._mapMarker) { row._mapMarker.setMap(null); row._mapMarker = null; }
    row.remove();
    updateVehicleCountInfo();
}

function updateVehicleCountInfo() {
    var rows = document.querySelectorAll('.vehicle-row');
    var filled = 0;
    rows.forEach(function(r) {
        var inputs = r.querySelectorAll('input');
        if (inputs[0].value && inputs[1].value) filled++;
    });
    var info = document.getElementById('vehicle-count-info');
    if (filled > 0) {
        info.textContent = '已设置 ' + filled + ' 辆车的位置';
        info.className = 'status-text success';
    } else {
        info.textContent = '未设置位置，将按站点均匀分配 ' + rows.length + ' 辆车';
        info.className = 'status-text';
    }
    var countInput = document.getElementById('p-vehicle-count');
    if (countInput && parseInt(countInput.value) !== rows.length) {
        countInput.value = rows.length;
    }
}

function collectVehicles() {
    var vehicles = [];
    var rows = document.querySelectorAll('.vehicle-row');
    rows.forEach(function(row, idx) {
        var inputs = row.querySelectorAll('input');
        var lng = parseFloat(inputs[0].value);
        var lat = parseFloat(inputs[1].value);
        if (!isNaN(lng) && !isNaN(lat)) {
            vehicles.push({
                vehicle_id: 'V' + (idx + 1 < 10 ? '0' : '') + (idx + 1),
                name: '云公交' + (idx + 1) + '号',
                lng: lng, lat: lat,
            });
        }
    });
    return vehicles;
}

function toggleMapPick() {
    if (!map) { alert('地图未加载，请稍后重试'); return; }
    mapPickMode = !mapPickMode;
    var btn = document.getElementById('btn-map-pick');
    if (mapPickMode) {
        btn.classList.add('active');
        btn.textContent = '取消选点';
        map.on('click', onMapClickForVehicle);
    } else {
        btn.classList.remove('active');
        btn.textContent = '地图选点';
        map.off('click', onMapClickForVehicle);
    }
}

function onMapClickForVehicle(e) {
    if (!mapPickMode) return;
    var lnglat = e.lnglat || e;
    var lng = lnglat.getLng();
    var lat = lnglat.getLat();
    var marker = new AMap.Marker({
        position: [lng, lat],
        content: '<div style="width:12px;height:12px;background:#ea4335;border-radius:50%;border:2px solid white;"></div>',
        offset: new AMap.Pixel(-6, -6),
        map: map,
    });
    var rows = document.querySelectorAll('.vehicle-row');
    var filled = false;
    for (var i = 0; i < rows.length; i++) {
        var inputs = rows[i].querySelectorAll('input');
        if (!inputs[0].value.trim() || !inputs[1].value.trim()) {
            inputs[0].value = lng.toFixed(4);
            inputs[1].value = lat.toFixed(4);
            rows[i]._mapMarker = marker;
            filled = true;
            break;
        }
    }
    if (!filled) addVehicleRow(lng.toFixed(4), lat.toFixed(4), marker);
    updateVehicleCountInfo();
}

// ---- 区域 WKT 文本解析 ----
function parseRegionWKT() {
    var wkt = document.getElementById('region-wkt-input').value.trim();
    if (!wkt) { setStatus('region-status', '请输入 WKT 文本', 'error'); return; }
    setStatus('region-status', '解析中...', '');
    fetch('/api/upload/region-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wkt: wkt }),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.detail) { setStatus('region-status', '错误: ' + data.detail, 'error'); return; }
        setStatus('region-status', '已解析: ' + data.vertex_count + ' 个顶点', 'success');
        dataLoaded.region = true;
        showRegion(data.vertices);
    })
    .catch(function(err) { setStatus('region-status', '解析失败: ' + err.message, 'error'); });
}

document.addEventListener('DOMContentLoaded', function() {
    var regionFile = document.getElementById('region-file');
    if (regionFile) {
        regionFile.addEventListener('change', function(e) {
            var file = e.target.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function(ev) {
                document.getElementById('region-wkt-input').value = ev.target.result.trim();
                parseRegionWKT();
            };
            reader.readAsText(file, 'UTF-8');
        });
    }
});

function loadAllSampleData() {
    loadSampleData('od');
    setTimeout(function() { loadSampleData('station'); }, 300);
    setTimeout(function() { loadSampleData('region'); }, 600);
}

function loadSampleData(type) {
    var url, statusId;
    if (type === 'od') { url = '/static/data/sample_od.csv'; statusId = 'od-status'; }
    else if (type === 'station') { url = '/static/data/sample_stations.csv'; statusId = 'station-status'; }
    else if (type === 'region') { url = '/static/data/sample_region.csv'; statusId = 'region-status'; }
    fetch(url)
    .then(function(resp) { return resp.text(); })
    .then(function(content) {
        if (type === 'od') {
            var blob = new Blob([content], { type: 'text/csv' });
            var file = new File([blob], 'sample_od.csv', { type: 'text/csv' });
            uploadFile('/api/upload/od', file, statusId, function(data) {
                var msg = '样例OD: ' + data.total_records + ' 条, 总需求 ' + data.total_demand;
                if (data.truncated) msg += ' (显示前1000条)';
                setStatus(statusId, msg, 'success');
                if (data.od_records && data.od_records.length > 0) showODLines(data.od_records);
            });
        } else if (type === 'station') {
            var blob = new Blob([content], { type: 'text/csv' });
            var file = new File([blob], 'sample_stations.csv', { type: 'text/csv' });
            uploadFile('/api/upload/stations', file, statusId, function(data) {
                setStatus(statusId, '样例站点: ' + data.total_stops + ' 个站点', 'success');
                showStations(data.stops);
            });
        } else if (type === 'region') {
            document.getElementById('region-wkt-input').value = content;
            parseRegionWKT();
            setStatus(statusId, '已加载样例区域边界', 'success');
        }
    })
    .catch(function(err) { setStatus(statusId, '加载样例数据失败: ' + err.message, 'error'); });
}

var helpLoaded = false;
function showHelp() {
    document.getElementById('help-modal').style.display = 'flex';
    if (!helpLoaded) {
        fetch('/api/help')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            document.getElementById('help-body').innerHTML = renderMarkdown(data.content);
            helpLoaded = true;
        })
        .catch(function(err) {
            document.getElementById('help-body').innerHTML = '<p style="color:red;">加载失败: ' + err.message + '</p>';
        });
    }
}

function closeHelp() { document.getElementById('help-modal').style.display = 'none'; }

document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) e.target.style.display = 'none';
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var modal = document.getElementById('help-modal');
        if (modal) modal.style.display = 'none';
    }
});

function renderMarkdown(md) {
    if (!md) return '';
    var html = md;
    html = html.replace(/```([\s\S]*?)```/g, function(m, code) { return '<pre><code>' + escapeHtml(code.trim()) + '</code></pre>'; });
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
    html = html.replace(/^---$/gm, '<hr>');
    html = html.replace(/^\|(.+)\|$/gm, function(match, content) {
        var cells = content.split('|').map(function(c) { return c.trim(); });
        if (cells.every(function(c) { return /^[-:]+$/.test(c); })) return '';
        return '<tr>' + cells.map(function(c) { return '<td>' + c + '</td>'; }).join('') + '</tr>';
    });
    html = html.replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, function(block) {
        var rows = block.trim().split('\n').filter(function(r) { return r.trim(); });
        if (rows.length === 0) return '';
        var header = rows[0].replace(/<td>/g, '<th>').replace(/<\/td>/g, '</th>');
        var body = rows.slice(1).join('\n');
        return '<table><thead>' + header + '</thead><tbody>' + body + '</tbody></table>';
    });
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>\n?)+/g, function(block) { return '<ul>' + block.trim() + '</ul>'; });
    html = html.replace(/^(?!<[hupoltb]|<hr|<li|<code|<pre|<block)(.+)$/gm, '<p>$1</p>');
    html = html.replace(/\n{2,}/g, '\n');
    return html;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}