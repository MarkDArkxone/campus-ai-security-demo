let activeAlarm = null;
let frameTimer = null;

function evidenceNumber(value) {
    return value == null ? "—" : Number(value).toFixed(3);
}

function updateRiskCards(payload) {
    for (const scene of payload.scenes || []) {
        const card = document.querySelector(`.risk-card[data-scene="${scene.scene}"]`);
        if (!card) continue;
        card.querySelector(".risk-number").textContent = evidenceNumber(scene.score);
        const values = [scene.belief, scene.plausibility, scene.unknown, scene.conflict];
        card.querySelectorAll("dd").forEach((element, index) => element.textContent = evidenceNumber(values[index]));
        const badge = card.querySelector(".status-badge");
        const statusLabels = {
            ready: "有效证据",
            conflict: "证据冲突",
            no_fusion_data: "暂无融合证据",
            rule_only: "规则检测",
            model_not_loaded: "模型未加载",
        };
        badge.textContent = scene.alarm_eligible ? "自动报警允许" : (statusLabels[scene.status] || scene.status || "状态未知");
        badge.className = `status-badge ${scene.conflict >= .6 ? "conflict" : scene.score >= .7 ? "high" : scene.score == null ? "muted" : "normal"}`;
        const available = scene.available_channels?.length ? scene.available_channels.join(" + ") : "—";
        const missing = scene.missing_channels?.length ? scene.missing_channels.join("、") : "—";
        card.querySelector("p").innerHTML = `参与通道：${escapeHtml(available)}<br>缺失通道：${escapeHtml(missing)}`;
    }
}

function updateMonitorStatus(payload) {
    const status = payload.status || {};
    const running = Boolean(status.running);
    const mode = document.getElementById("videoMode");
    const source = document.getElementById("videoSourceLabel");
    const camera = document.getElementById("cameraSummary");
    const detail = document.getElementById("cameraDetail");
    const sensor = status.sensor_simulator || {};
    const sensorSummary = document.getElementById("sensorSummary");
    const sensorDetail = document.getElementById("sensorDetail");
    if (mode) { mode.textContent = running ? (status.mock_video_mode ? "模拟画面" : "实时画面") : "分析已停止"; mode.className = `status-badge ${running ? "info" : "muted"}`; }
    if (source) source.textContent = `视频源：${status.video_source ?? "—"}`;
    if (camera) { camera.textContent = running ? (status.mock_video_mode ? "在线 · 模拟模式" : "在线 · 实时采集") : "已停止"; camera.className = running ? "" : "muted-text"; }
    if (detail) detail.textContent = status.last_error ? `最近错误：${status.last_error}` : `最近帧 ${running ? "持续更新" : "—"}`;
    if (sensorSummary) sensorSummary.textContent = sensor.running ? "在线 · 模拟采集" : "模拟任务已停止";
    if (sensorDetail) sensorDetail.textContent = sensor.last_error ? `最近错误：${sensor.last_error}` : "数据周期 3.0s";
    document.getElementById("lastFrameAt").textContent = running ? "刚刚" : "—";
    document.getElementById("captureFps").textContent = running ? (status.mock_video_mode ? "~16.7" : "—") : "—";
    document.getElementById("detectFps").textContent = running ? "—" : "—";
}

function showCurrentAlarm(alarm) {
    activeAlarm = alarm;
    const banner = document.getElementById("currentAlarmBanner");
    banner?.classList.remove("hidden");
    document.getElementById("bannerType").textContent = `${alarm.event_type} · ${alarm.event_level === "high" ? "高风险" : "待确认"}`;
    document.getElementById("bannerMessage").textContent = alarm.message;
    document.getElementById("bannerMeta").textContent = `触发来源：${alarm.event_type.includes("warning") ? "sensor" : "video / business"} · ${formatTime(alarm.created_at)} · ${alarm.location || "未标注位置"}`;
}

async function acknowledgeCurrentAlarm() {
    if (!activeAlarm?.id) {
        document.getElementById("currentAlarmBanner")?.classList.add("hidden");
        showToast("实时推送未包含事件编号，请到报警事件页确认");
        return;
    }
    await requestJson(`/api/alarms/${activeAlarm.id}/acknowledge`, { method: "POST" });
    document.getElementById("currentAlarmBanner")?.classList.add("hidden");
    showToast("报警已确认");
}

function saveVideoSnapshot() {
    const image = document.getElementById("videoFeed");
    if (!image?.naturalWidth) return showToast("当前画面尚未就绪", "error");
    try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        canvas.getContext("2d").drawImage(image, 0, 0);
        const link = document.createElement("a");
        link.download = `campus-monitor-${Date.now()}.jpg`;
        link.href = canvas.toDataURL("image/jpeg", .92);
        link.click();
        showToast("当前画面截图已保存");
    } catch (error) {
        showToast(`截图失败：${error.message}`, "error");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const videoFeed = document.getElementById("videoFeed");
    if (videoFeed) videoFeed.src = window.CampusAPI.videoFeedUrl();
    const refresh = () => Promise.all([
        refreshHealth().then(updateMonitorStatus),
        requestJson(window.CampusAPI.endpoints.evidenceCurrent).then(updateRiskCards),
    ]).catch(() => {});
    refresh();
    frameTimer = setInterval(refresh, 2500);
    connectAlarmSocket(showCurrentAlarm);
    document.getElementById("snapshotBtn")?.addEventListener("click", saveVideoSnapshot);
    document.getElementById("videoFullscreenBtn")?.addEventListener("click", () => {
        const panel = document.getElementById("videoPanel");
        document.fullscreenElement ? document.exitFullscreen() : panel?.requestFullscreen();
    });
    document.getElementById("boxToggle")?.addEventListener("click", event => {
        event.currentTarget.classList.toggle("active");
        document.getElementById("videoFeed")?.classList.toggle("boxes-hidden");
        showToast("当前检测框由后端合成，此开关仅弱化叠加画面");
    });
    document.getElementById("ackAlarmBtn")?.addEventListener("click", () => acknowledgeCurrentAlarm().catch(error => showToast(error.message, "error")));
    document.getElementById("mute30Btn")?.addEventListener("click", () => muteAlarms(30));
});
