(function createCampusApi(global) {
    "use strict";

    const runtime = Object.freeze({
        apiBaseUrl: String(global.CAMPUS_RUNTIME_CONFIG?.apiBaseUrl || "").replace(/\/$/, ""),
        wsBaseUrl: String(global.CAMPUS_RUNTIME_CONFIG?.wsBaseUrl || "").replace(/\/$/, ""),
        contractVersion: String(global.CAMPUS_RUNTIME_CONFIG?.contractVersion || "1.0"),
        requestTimeoutMs: Number(global.CAMPUS_RUNTIME_CONFIG?.requestTimeoutMs || 12000),
    });

    const endpoints = Object.freeze({
        health: "/api/health",
        integrationManifest: "/api/integration/manifest",
        dashboardStats: "/api/dashboard/stats",
        evidenceCurrent: "/api/evidence/current",
        evidenceTrends: "/api/evidence/trends",
        devicesSummary: "/api/devices/summary",
        systemDiagnostics: "/api/system/diagnostics",
        alarms: "/api/alarms",
        acknowledgeAlarm: id => `/api/alarms/${encodeURIComponent(id)}/acknowledge`,
        startDetection: "/api/start",
        stopDetection: "/api/stop",
        config: "/api/config",
        videoFeed: "/video_feed",
        alarmSocket: "/ws/alarms",
        persons: "/api/persons",
        accessDevices: "/api/access/devices",
        accessRecords: "/api/access/records",
        accessSimulate: "/api/access/simulate",
        visitors: "/api/visitors",
        visitorApprove: id => `/api/visitors/${encodeURIComponent(id)}/approve`,
        visitorReject: id => `/api/visitors/${encodeURIComponent(id)}/reject`,
        visitorEntry: id => `/api/visitors/${encodeURIComponent(id)}/simulate-entry`,
        sensors: "/api/sensors",
        sensorData: "/api/sensor-data",
        sensorSimulationStart: "/api/sensors/simulate/start",
        sensorSimulationStop: "/api/sensors/simulate/stop",
        sensorAbnormal: type => `/api/sensors/simulate/abnormal?sensor_type=${encodeURIComponent(type)}`,
        mapPoints: "/api/map-points",
        users: "/api/users",
        demoInit: "/api/demo/init",
        demoRun: "/api/demo/run",
        demoTrigger: type => `/api/demo/trigger/${encodeURIComponent(type)}`,
    });

    class CampusApiError extends Error {
        constructor(message, status, payload) {
            super(message);
            this.name = "CampusApiError";
            this.status = status;
            this.payload = payload;
        }
    }

    function joinBase(base, path) {
        if (/^https?:\/\//i.test(path)) return path;
        const normalizedPath = path.startsWith("/") ? path : `/${path}`;
        return base ? `${base}${normalizedPath}` : normalizedPath;
    }

    function httpUrl(path) {
        return joinBase(runtime.apiBaseUrl, path);
    }

    function websocketUrl(path = endpoints.alarmSocket) {
        const normalizedPath = path.startsWith("/") ? path : `/${path}`;
        let result;
        if (runtime.wsBaseUrl) result = `${runtime.wsBaseUrl}${normalizedPath}`;
        else if (runtime.apiBaseUrl) {
            const url = new URL(runtime.apiBaseUrl);
            url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
            result = `${url.origin}${url.pathname.replace(/\/$/, "")}${normalizedPath}`;
        } else {
            const protocol = location.protocol === "https:" ? "wss:" : "ws:";
            result = `${protocol}//${location.host}${normalizedPath}`;
        }
        const token = sessionStorage.getItem("campus_access_token");
        if (token) {
            const url = new URL(result);
            url.searchParams.set("access_token", token);
            return url.toString();
        }
        return result;
    }

    function assetUrl(path) {
        if (!path || /^(https?:)?\/\//i.test(path) || path.startsWith("data:")) return path;
        return httpUrl(path);
    }

    function setAccessToken(token) {
        if (token) sessionStorage.setItem("campus_access_token", token);
        else sessionStorage.removeItem("campus_access_token");
    }

    async function request(path, options = {}) {
        const controller = new AbortController();
        const timeoutMs = Number(options.timeoutMs || runtime.requestTimeoutMs);
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        const headers = new Headers(options.headers || {});
        headers.set("Accept", "application/json");
        headers.set("X-Campus-Contract-Version", runtime.contractVersion);
        const token = sessionStorage.getItem("campus_access_token");
        if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);

        let body = options.body;
        if (body && typeof body === "object" && !(body instanceof FormData) && !(body instanceof Blob)) {
            headers.set("Content-Type", "application/json");
            body = JSON.stringify(body);
        }
        if (options.signal) {
            if (options.signal.aborted) controller.abort();
            else options.signal.addEventListener("abort", () => controller.abort(), { once: true });
        }

        try {
            const response = await fetch(httpUrl(path), {
                ...options,
                body,
                headers,
                signal: controller.signal,
                credentials: options.credentials || "include",
            });
            const contentType = response.headers.get("content-type") || "";
            const payload = contentType.includes("application/json") ? await response.json() : await response.text();
            if (!response.ok) {
                const detail = typeof payload === "object" ? payload.detail || payload.message : payload;
                throw new CampusApiError(detail || `请求失败 (${response.status})`, response.status, payload);
            }
            return payload;
        } catch (error) {
            if (error.name === "AbortError") throw new CampusApiError(`请求超时 (${timeoutMs}ms)`, 0, null);
            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    global.CampusAPI = Object.freeze({
        runtime,
        endpoints,
        CampusApiError,
        request,
        httpUrl,
        websocketUrl,
        assetUrl,
        setAccessToken,
        videoFeedUrl: () => httpUrl(endpoints.videoFeed),
    });
})(window);
