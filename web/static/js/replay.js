let replayData = null;       // 轨迹数据 {vehicle_id: [[time, lng, lat, status], ...]}
let replayStartTime = 0;     // 仿真起始时间
let replayEndTime = 0;       // 仿真结束时间
let replayCurrentTime = 0;   // 当前回放时间
let replayPlaying = false;
let replayTimer = null;
let replaySpeed = 5;         // 回放倍速

/**
 * 加载轨迹数据并开始回放
 */
function loadTrajectory(trajectories, simStart, simEnd) {
    replayData = trajectories;
    replayStartTime = simStart;
    replayEndTime = simEnd;
    replayCurrentTime = simStart;

    // 显示回放控制条
    document.getElementById('replay-bar').classList.remove('hidden');

    // 设置滑块范围
    var slider = document.getElementById('replay-slider');
    slider.min = 0;
    slider.max = simEnd - simStart;
    slider.value = 0;

    // 在地图上显示车辆
    showVehicleMarkers(trajectories);
    updateReplayDisplay();

    // 自动缩放到车辆范围
    var allMarkers = [];
    for (var vid in vehicleMarkers) {
        allMarkers.push(vehicleMarkers[vid].marker);
    }
    if (allMarkers.length > 0 && typeof map !== 'undefined' && map) {
        map.setFitView(allMarkers, false, [60, 60, 60, 60]);
    }
}

/**
 * 切换播放/暂停
 */
function togglePlay() {
    if (replayPlaying) {
        pauseReplay();
    } else {
        startReplay();
    }
}

function startReplay() {
    if (!replayData) return;
    replayPlaying = true;
    document.getElementById('btn-play').textContent = '暂停';

    if (replayTimer) clearInterval(replayTimer);
    replayTimer = setInterval(function() {
        replayCurrentTime += replaySpeed;
        if (replayCurrentTime >= replayEndTime) {
            replayCurrentTime = replayEndTime;
            pauseReplay();
        }
        updateReplayDisplay();
    }, 100);  // 每 100ms 更新一次
}

function pauseReplay() {
    replayPlaying = false;
    document.getElementById('btn-play').textContent = '播放';
    if (replayTimer) {
        clearInterval(replayTimer);
        replayTimer = null;
    }
}

/**
 * 拖动滑块跳转
 */
function seekReplay(value) {
    replayCurrentTime = replayStartTime + parseFloat(value);
    updateReplayDisplay();
}

/**
 * 设置回放速度
 */
function setReplaySpeed(value) {
    replaySpeed = parseFloat(value);
}

/**
 * 更新回放显示
 */
function updateReplayDisplay() {
    // 更新时间显示 - 显示实际仿真时刻 (如 7:00:00 ~ 9:00:00)
    var hours = Math.floor(replayCurrentTime / 3600);
    var minutes = Math.floor((replayCurrentTime % 3600) / 60);
    var seconds = Math.floor(replayCurrentTime % 60);
    var timeStr = hours + ':' + String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
    document.getElementById('replay-time').textContent = timeStr;

    // 更新滑块位置
    var slider = document.getElementById('replay-slider');
    slider.value = replayCurrentTime - replayStartTime;

    // 更新车辆位置
    updateVehiclePositions(replayCurrentTime);
}

/**
 * 清理回放
 */
function clearReplay() {
    pauseReplay();
    replayData = null;
    document.getElementById('replay-bar').classList.add('hidden');
    clearVehicleMarkers();
}