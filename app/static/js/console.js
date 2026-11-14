let eventRecords = [];
let selectedEvent = null;
let eventPage = 1;
const eventPageSize = 30;

function sceneForType(type) {
    if (["fire_detected", "smoke_detected", "fire_risk_high"].includes(type)) return "fire";
    if (/fall/.test(type)) return "fall";
    if (/fight/.test(type)) return "fight";
    if (/fence/.test(type)) return "fence";
    if (/crowd/.test(type)) return "crowd";
    if (/access/.test(type)) return "access";
    return "sensor";
}

function eventRows(records) {
    return records.map(event => `<tr><td>${formatTime(event.created_at)}</td><td>#${event.id}</td><td><code>${escapeHtml(event.event_type)}</code></td><td>置信度 ${event.confidence == null ? "—" : Number(event.confidence).toFixed(3)}<br><span class="muted">DS：—</span></td><td><span class="${levelClass(event.event_level)}">${escapeHtml(event.event_level)}</span></td><td>${escapeHtml(event.location || "—")}</td><td><span class="${statusClass(event.status)}">${event.status === "handled" ? "已确认" : "未确认"}</span></td><td>${event.snapshot_path ? `<a href="${encodeURI(window.CampusAPI.assetUrl(event.snapshot_path))}" target="_blank" rel="noopener">查看截图</a>` : "—"}</td><td><button class="btn secondary compact" data-event-detail="${event.id}">查看详情</button></td></tr>`).join("");
}

function applyEventFilters() {
    const type = document.getElementById("eventTypeFilter")?.value || "";
    const level = document.getElementById("eventLevelFilter")?.value || "";
    const id = document.getElementById("eventIdFilter")?.value || "";
    const status = document.getElementById("eventStatusFilter")?.value || "";
    const filtered = eventRecords.filter(event => (!type || sceneForType(event.event_type) === type) && (!level || event.event_level === level) && (!id || String(event.id) === id) && (!status || event.status === status));
    const pageCount = Math.max(1, Math.ceil(filtered.length / eventPageSize));
    eventPage = Math.min(eventPage, pageCount);
    const pageRecords = filtered.slice((eventPage - 1) * eventPageSize, eventPage * eventPageSize);
    const body = document.getElementById("alarmTableBody");
    if (body) body.innerHTML = pageRecords.length ? eventRows(pageRecords) : `<tr><td colspan="9" class="empty-cell">没有符合条件的报警事件</td></tr>`;
    const count = document.getElementById("eventCountText");
    if (count) count.textContent = `共 ${filtered.length} 条事件`;
    const label = document.getElementById("eventPageLabel");
    if (label) label.textContent = `第 ${eventPage} / ${pageCount} 页`;
    const previous = document.getElementById("previousEventPage");
    const next = document.getElementById("nextEventPage");
    if (previous) previous.disabled = eventPage <= 1;
    if (next) next.disabled = eventPage >= pageCount;
}

async function loadEventRecords() {
    eventRecords = await requestJson("/api/alarms");
    applyEventFilters();
}

function openEventDrawer(id) {
    selectedEvent = eventRecords.find(event => event.id === id);
    if (!selectedEvent) return;
    const content = document.getElementById("eventDetailContent");
    const snapshotUrl = selectedEvent.snapshot_path ? window.CampusAPI.assetUrl(selectedEvent.snapshot_path) : null;
    content.innerHTML = `<section class="detail-section"><h3>基础信息</h3><div class="detail-grid"><div><span>事件编号</span><b>#${selectedEvent.id}</b></div><div><span>场景</span><b>${escapeHtml(selectedEvent.event_type)}</b></div><div><span>时间</span><b>${formatTime(selectedEvent.created_at)}</b></div><div><span>等级</span><b>${escapeHtml(selectedEvent.event_level)}</b></div><div><span>位置</span><b>${escapeHtml(selectedEvent.location || "—")}</b></div><div><span>确认状态</span><b>${selectedEvent.status === "handled" ? "已确认" : "未确认"}</b></div></div></section><section class="detail-section"><h3>证据诊断</h3><div class="detail-grid"><div><span>检测置信度</span><b>${selectedEvent.confidence == null ? "—" : Number(selectedEvent.confidence).toFixed(3)}</b></div><div><span>人员数量</span><b>${selectedEvent.person_count ?? "—"}</b></div><div><span>Bel / Pl</span><b>— / —</b></div><div><span>Unknown / Conflict</span><b>— / —</b></div></div><p class="muted">当前事件未保存 DS 融合字段，缺失值不会显示为 0。</p></section><section class="detail-section"><h3>事件消息</h3><p>${escapeHtml(selectedEvent.message)}</p></section>${snapshotUrl ? `<section class="detail-section"><h3>现场截图</h3><a href="${encodeURI(snapshotUrl)}" target="_blank" rel="noopener"><img class="detail-snapshot" src="${encodeURI(snapshotUrl)}" alt="报警截图"></a></section>` : `<section class="detail-section"><h3>现场资料</h3><div class="empty-inline">该事件没有关联截图</div></section>`}`;
    document.getElementById("eventDrawer")?.classList.add("open");
    document.getElementById("eventDrawer")?.setAttribute("aria-hidden", "false");
    document.getElementById("drawerBackdrop")?.classList.remove("hidden");
}

function closeEventDrawer() {
    document.getElementById("eventDrawer")?.classList.remove("open");
    document.getElementById("eventDrawer")?.setAttribute("aria-hidden", "true");
    document.getElementById("drawerBackdrop")?.classList.add("hidden");
}

async function acknowledgeSelectedEvent() {
    if (!selectedEvent) return;
    await requestJson(`/api/alarms/${selectedEvent.id}/acknowledge`, { method: "POST" });
    selectedEvent.status = "handled";
    await loadEventRecords();
    openEventDrawer(selectedEvent.id);
    showToast("事件已确认");
}

function exportSelectedEvent() {
    if (!selectedEvent) return;
    const blob = new Blob([JSON.stringify(selectedEvent, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `alarm-event-${selectedEvent.id}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
}

async function loadDeviceConsole() {
    const [health, sensors, accessDevices] = await Promise.all([requestJson("/api/health"), requestJson("/api/sensors"), requestJson("/api/access/devices")]);
    const status = health.status || {};
    document.getElementById("deviceVideoSource").textContent = status.video_source ?? "—";
    document.getElementById("deviceVideoError").textContent = status.last_error || "无";
    const badge = document.getElementById("cameraStatusBadge");
    badge.textContent = status.running ? (status.mock_video_mode ? "模拟在线" : "在线") : "已停止";
    badge.className = `status-badge ${status.running ? "normal" : "muted"}`;
    document.getElementById("sensorDeviceBadge").textContent = status.sensor_simulator?.running ? "模拟运行中" : "模拟已停止";
    document.getElementById("sensorDeviceSummary").innerHTML = `<div><dt>连接模式</dt><dd>本地模拟</dd></div><div><dt>设备数量</dt><dd>${sensors.length}</dd></div><div><dt>在线设备</dt><dd>${sensors.filter(item => item.status === "online").length}</dd></div><div><dt>模拟周期</dt><dd>3.0s</dd></div>`;
    document.getElementById("accessDeviceBody").innerHTML = accessDevices.map(device => `<tr><td>#${device.id}</td><td>${escapeHtml(device.name)}</td><td>${escapeHtml(device.location || "—")}</td><td>${escapeHtml(device.device_type)}</td><td><span class="${statusClass(device.status)}">${escapeHtml(device.status)}</span></td></tr>`).join("") || `<tr><td colspan="5" class="empty-cell">暂无门禁设备</td></tr>`;
    document.getElementById("deviceDiagnostics").textContent = JSON.stringify(status, null, 2);
    return status;
}

async function loadSystemDiagnostics() {
    const health = await requestJson("/api/health");
    const status = health.status || {};
    document.getElementById("systemDiagnostics").textContent = JSON.stringify(health, null, 2);
    const config = status.config || {};
    document.getElementById("fallFramesSetting").textContent = config.fall_consecutive_frames ?? "—";
    document.getElementById("cooldownSetting").textContent = config.alarm_cooldown_seconds == null ? "—" : `${config.alarm_cooldown_seconds}s`;
    document.getElementById("personModelSource").textContent = config.model_name || "yolov8n.pt / mock fallback";
    document.getElementById("fireModelSource").textContent = config.fire_model_path || "OpenCV HSV 规则";
    return health;
}

function initAnalysisPage() {
    const formatMetric = value => value == null ? "—" : Number(value).toFixed(3);
    const loadEvidence = async () => {
        const payload = await requestJson(window.CampusAPI.endpoints.evidenceCurrent);
        for (const scene of payload.scenes || []) {
            const card = document.querySelector(`[data-scene-card="${scene.scene}"]`);
            if (!card) continue;
            card.querySelector(".ds-score strong").textContent = formatMetric(scene.score);
            const values = [scene.belief, scene.plausibility, scene.unknown, scene.conflict];
            card.querySelectorAll(".ds-metrics b").forEach((element, index) => element.textContent = formatMetric(values[index]));
            card.querySelector("p").innerHTML = `参与：${escapeHtml(scene.available_channels?.join(" + ") || "—")}<br>缺失：${escapeHtml(scene.missing_channels?.join("、") || "—")}`;
        }
        const notice = document.querySelector(".evidence-notice");
        if (notice && payload.fusion_available) {
            notice.innerHTML = "<strong>DS 融合后端已连接</strong><span>页面展示的数据由后端提供，前端不参与风险计算。</span>";
        }
    };
    const applyScene = () => {
        const value = document.getElementById("sceneFilter").value;
        document.querySelectorAll("[data-scene-card]").forEach(card => card.classList.toggle("hidden", value !== "all" && card.dataset.sceneCard !== value));
    };
    const queryScene = new URLSearchParams(location.search).get("scene");
    if (["fire", "fall", "fight"].includes(queryScene)) document.getElementById("sceneFilter").value = queryScene;
    document.getElementById("sceneFilter")?.addEventListener("change", applyScene);
    document.getElementById("pauseAnalysis")?.addEventListener("click", event => { event.currentTarget.classList.toggle("active"); event.currentTarget.textContent = event.currentTarget.classList.contains("active") ? "继续实时更新" : "暂停实时更新"; });
    document.getElementById("exportEvidence")?.addEventListener("click", () => showToast("当前没有可导出的 DS 证据数据"));
    applyScene();
    loadEvidence().catch(error => showToast(`证据接口不可用：${error.message}`, "error"));
}

function initEventsPage() {
    loadEventRecords().catch(error => showToast(error.message, "error"));
    document.getElementById("queryEventsBtn")?.addEventListener("click", () => { eventPage = 1; applyEventFilters(); });
    document.getElementById("resetEventsBtn")?.addEventListener("click", () => { ["eventTypeFilter", "eventLevelFilter", "eventIdFilter", "eventStatusFilter"].forEach(id => document.getElementById(id).value = ""); eventPage = 1; applyEventFilters(); });
    document.getElementById("previousEventPage")?.addEventListener("click", () => { eventPage = Math.max(1, eventPage - 1); applyEventFilters(); });
    document.getElementById("nextEventPage")?.addEventListener("click", () => { eventPage += 1; applyEventFilters(); });
    document.getElementById("refreshAlarmsBtn")?.addEventListener("click", () => loadEventRecords().catch(error => showToast(error.message, "error")));
    document.getElementById("alarmTableBody")?.addEventListener("click", event => { const button = event.target.closest("[data-event-detail]"); if (button) openEventDrawer(Number(button.dataset.eventDetail)); });
    ["closeDrawerBtn", "drawerCloseBtn", "drawerBackdrop"].forEach(id => document.getElementById(id)?.addEventListener("click", closeEventDrawer));
    document.getElementById("drawerAckBtn")?.addEventListener("click", () => acknowledgeSelectedEvent().catch(error => showToast(error.message, "error")));
    document.getElementById("exportEventBtn")?.addEventListener("click", exportSelectedEvent);
    connectAlarmSocket(() => loadEventRecords().catch(() => {}));
}

function initDevicesPage() {
    let diagnostics = null;
    const load = () => loadDeviceConsole().then(data => diagnostics = data).catch(error => showToast(error.message, "error"));
    load();
    document.getElementById("refreshDevicesBtn")?.addEventListener("click", load);
    document.getElementById("copyDiagnosticsBtn")?.addEventListener("click", () => navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2)).then(() => showToast("设备诊断已复制")).catch(() => showToast("复制失败", "error")));
    document.getElementById("reconnectVideoBtn")?.addEventListener("click", async () => { await requestJson("/api/stop", { method: "POST" }); await requestJson("/api/start", { method: "POST" }); showToast("视频设备已重新连接"); load(); });
    document.querySelector("[data-sensor-action='normal']")?.addEventListener("click", () => requestJson("/api/sensors/simulate/start", { method: "POST" }).then(() => showToast("正常模拟数据已恢复")).then(load));
    document.querySelector("[data-sensor-action='smoke']")?.addEventListener("click", () => requestJson("/api/sensors/simulate/abnormal?sensor_type=smoke", { method: "POST" }).then(() => showToast("已生成烟雾高值数据")));
    document.getElementById("stopSensorSimulation")?.addEventListener("click", () => { if (confirm("停止后传感器数据将不再更新。确认模拟断开？")) requestJson("/api/sensors/simulate/stop", { method: "POST" }).then(load); });
    document.getElementById("startSensorSimulation")?.addEventListener("click", () => requestJson("/api/sensors/simulate/start", { method: "POST" }).then(load));
}

function initSettingsPage() {
    let diagnostics = null;
    const load = () => loadSystemDiagnostics().then(data => diagnostics = data).catch(error => showToast(error.message, "error"));
    load();
    document.getElementById("refreshDiagnosticsBtn")?.addEventListener("click", load);
    document.getElementById("copySystemDiagnosticsBtn")?.addEventListener("click", () => navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2)).then(() => showToast("系统诊断已复制")).catch(() => showToast("复制失败", "error")));
    const sound = document.getElementById("soundSetting");
    sound.checked = localStorage.getItem("alarmSoundEnabled") !== "false";
    sound.addEventListener("change", () => { localStorage.setItem("alarmSoundEnabled", String(sound.checked)); if (!sound.checked) muteAlarms(86400); else { consoleState.mutedUntil = 0; sessionStorage.removeItem("alarmMutedUntil"); } });
}

document.addEventListener("DOMContentLoaded", () => {
    const page = document.body.dataset.page;
    if (page === "analysis") initAnalysisPage();
    if (page === "events") initEventsPage();
    if (page === "devices") initDevicesPage();
    if (page === "settings") initSettingsPage();
});
