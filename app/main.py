import asyncio
from datetime import datetime

from fastapi import Depends, FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.alarm_manager import alarm_manager
from app.auth import authenticate_user, hash_password
from app.config import (
    API_CONTRACT_VERSION,
    BASE_DIR,
    CORS_ALLOWED_ORIGINS,
    FRONTEND_API_BASE_URL,
    FRONTEND_WS_BASE_URL,
    SECRET_KEY,
    runtime_config,
)
from app.database import SessionLocal, get_db, init_db
from app.dependencies import get_current_user, require_api_roles, user_context
from app.models import (
    AccessDevice,
    AccessRecord,
    AlarmEvent,
    MapPoint,
    Person,
    SensorData,
    SensorDevice,
    User,
    VisitorRecord,
)
from app.schemas import (
    AccessSimulateIn,
    AlarmEventOut,
    ApiResponse,
    ConfigUpdate,
    MapPointIn,
    PersonIn,
    SensorIn,
    UserIn,
    UserUpdate,
    VisitorIn,
)
from app.services.access_service import simulate_access, simulate_visitor_entry
from app.services.dashboard_service import dashboard_stats
from app.services.demo_service import initialize_demo_data, run_demo_sequence, trigger_demo_alarm
from app.services.init_service import seed_defaults
from app.services.sensor_service import sensor_simulator
from app.services.video_service import video_service
from app.services.websocket_manager import websocket_manager


app = FastAPI(title="Campus AI Security Demo", version="2.0.0")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
if CORS_ALLOWED_ORIGINS:
    allow_all_origins = "*" in CORS_ALLOWED_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all_origins else CORS_ALLOWED_ORIGINS,
        allow_credentials=not allow_all_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Campus-Contract-Version"],
    )
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
FRONTEND_CONFIG = {
    "apiBaseUrl": FRONTEND_API_BASE_URL,
    "wsBaseUrl": FRONTEND_WS_BASE_URL,
    "contractVersion": API_CONTRACT_VERSION,
    "requestTimeoutMs": 12000,
}
templates.env.globals["frontend_config"] = FRONTEND_CONFIG

ALLOWED_SENSOR_TYPES = {"smoke", "temperature", "current", "voltage", "humidity"}
ALLOWED_PERSON_ROLES = {"student", "teacher", "staff", "visitor", "blacklist"}
ALLOWED_PERSON_STATUSES = {"normal", "disabled", "blacklist"}
ALLOWED_DEVICE_TYPES = {"gate", "face_terminal", "card_reader"}
ALLOWED_DEVICE_STATUSES = {"online", "offline"}
ALLOWED_ACCESS_TYPES = {"entry", "exit"}
ALLOWED_AUTH_METHODS = {"face", "card", "qrcode", "manual"}
ALLOWED_VISITOR_STATUSES = {"pending", "approved", "rejected", "expired"}
ALLOWED_MAP_POINT_TYPES = {"camera", "access", "sensor", "alarm_area"}
ALLOWED_MAP_POINT_STATUSES = {"normal", "warning", "alarm", "offline"}
ALLOWED_USER_ROLES = {"admin", "security", "teacher", "viewer"}


def render_page(request: Request, template: str, user: User, extra: dict | None = None):
    context = {"request": request, "frontend_config": FRONTEND_CONFIG, **user_context(user)}
    if extra:
        context.update(extra)
    return templates.TemplateResponse(request, template, context)


def page_guard(request: Request, user: User | None, roles: set[str] | None = None):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if roles and user.role not in roles:
        return templates.TemplateResponse(
            request,
            "403.html",
            {"request": request, "frontend_config": FRONTEND_CONFIG, **user_context(user)},
            status_code=403,
        )
    return None


def parse_datetime_query(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} datetime format") from exc


def get_websocket_user(websocket: WebSocket) -> User | None:
    user_id = websocket.session.get("user_id")
    if not user_id:
        return None
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None
    with SessionLocal() as db:
        user = db.get(User, user_id_int)
        if not user or not user.is_active:
            return None
        return user


def ensure_allowed(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")


def validate_person_payload(payload: PersonIn) -> None:
    ensure_allowed(payload.role, ALLOWED_PERSON_ROLES, "role")
    ensure_allowed(payload.status, ALLOWED_PERSON_STATUSES, "status")


def validate_sensor_payload(payload: SensorIn) -> None:
    ensure_allowed(payload.sensor_type, ALLOWED_SENSOR_TYPES, "sensor_type")
    ensure_allowed(payload.status, ALLOWED_DEVICE_STATUSES, "status")
    if payload.threshold_value < 0:
        raise HTTPException(status_code=400, detail="threshold_value must be non-negative")


def validate_map_point_payload(payload: MapPointIn) -> None:
    ensure_allowed(payload.point_type, ALLOWED_MAP_POINT_TYPES, "point_type")
    ensure_allowed(payload.status, ALLOWED_MAP_POINT_STATUSES, "status")
    if not 0 <= payload.x <= 100 or not 0 <= payload.y <= 100:
        raise HTTPException(status_code=400, detail="Map point x/y must be between 0 and 100")


def validate_user_role(role: str | None) -> None:
    if role is not None:
        ensure_allowed(role, ALLOWED_USER_ROLES, "role")


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)
    alarm_manager.set_event_loop(asyncio.get_running_loop())
    sensor_simulator.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    video_service.stop()
    sensor_simulator.stop()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(request, "login.html", {"request": request, "error": "用户名或密码错误"}, status_code=400)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user)
    if blocked:
        return blocked
    return render_page(request, "index.html", user)


@app.get("/monitor", response_class=HTMLResponse)
async def monitor(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security"})
    if blocked:
        return blocked
    return render_page(request, "monitor.html", user)


@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security", "teacher"})
    if blocked:
        return blocked
    return render_page(request, "analysis.html", user)


@app.get("/alarms", response_class=HTMLResponse)
@app.get("/events", response_class=HTMLResponse)
async def alarms_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security", "teacher"})
    if blocked:
        return blocked
    return render_page(request, "alarms.html", user)


@app.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security"})
    if blocked:
        return blocked
    return render_page(request, "devices.html", user)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security"})
    if blocked:
        return blocked
    return render_page(request, "settings.html", user)


@app.get("/access", response_class=HTMLResponse)
@app.get("/access/persons", response_class=HTMLResponse)
async def access_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security"})
    if blocked:
        return blocked
    return render_page(request, "access.html", user)


@app.get("/visitors", response_class=HTMLResponse)
async def visitors_redirect(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security", "teacher"})
    if blocked:
        return blocked
    return render_page(request, "visitors.html", user)


@app.get("/sensors", response_class=HTMLResponse)
async def sensors_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security"})
    if blocked:
        return blocked
    return render_page(request, "sensors.html", user)


@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security", "teacher", "viewer"})
    if blocked:
        return blocked
    return render_page(request, "map.html", user)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin", "security", "teacher", "viewer"})
    if blocked:
        return blocked
    return render_page(request, "dashboard.html", user)


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: User | None = Depends(get_current_user)):
    blocked = page_guard(request, user, {"admin"})
    if blocked:
        return blocked
    return render_page(request, "users.html", user)


@app.get("/video_feed")
async def video_feed(user: User | None = Depends(get_current_user)):
    if not user or user.role not in {"admin", "security"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return StreamingResponse(video_service.mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/health")
async def api_health():
    status = video_service.status()
    status["sensor_simulator"] = {"running": sensor_simulator.running, "last_error": sensor_simulator.last_error}
    return {"ok": True, "service": "campus_ai_security_demo", "status": status}


@app.get("/api/integration/manifest")
async def api_integration_manifest():
    """Machine-readable summary for a replacement backend implementation."""
    return {
        "contract_version": API_CONTRACT_VERSION,
        "authentication": {"default": "session_cookie", "optional_frontend": "bearer_token"},
        "transports": {
            "rest_prefix": "/api",
            "alarm_websocket": "/ws/alarms",
            "video_stream": "/video_feed",
        },
        "required_endpoints": [
            "GET /api/health",
            "GET /api/dashboard/stats",
            "GET /api/alarms",
            "POST /api/alarms/{id}/acknowledge",
            "POST /api/start",
            "POST /api/stop",
            "GET /api/persons",
            "GET /api/access/devices",
            "GET /api/access/records",
            "GET /api/visitors",
            "GET /api/sensors",
            "GET /api/sensor-data",
            "GET /api/map-points",
            "GET /api/evidence/current",
            "GET /api/evidence/trends",
            "GET /api/devices/summary",
            "GET /api/system/diagnostics",
        ],
        "optional_endpoints": [
            "POST /api/config",
            "POST /api/demo/init",
            "POST /api/demo/run",
            "POST /api/demo/trigger/{alarm_type}",
            "GET /api/users",
        ],
        "websocket_event": {
            "id": "integer",
            "event_type": "string",
            "event_level": "low|medium|high",
            "message": "string",
            "location": "string",
            "snapshot_path": "string|null",
            "person_count": "integer",
            "confidence": "number|null",
            "created_at": "ISO-8601 datetime",
            "status": "unhandled|handled",
            "map_point_id": "integer|null",
        },
    }


@app.get("/api/evidence/current")
async def api_evidence_current(user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    """Stable extension point for a future DS/multimodal fusion backend."""
    now = datetime.now().isoformat()
    return {
        "contract_version": API_CONTRACT_VERSION,
        "fusion_available": False,
        "scenes": [
            {
                "scene": "fire",
                "score": None,
                "belief": None,
                "disbelief": None,
                "plausibility": None,
                "unknown": None,
                "conflict": None,
                "alarm_eligible": False,
                "status": "no_fusion_data",
                "available_channels": ["video"],
                "missing_channels": ["audio", "ds_fusion"],
                "updated_at": now,
            },
            {
                "scene": "fall",
                "score": None,
                "belief": None,
                "disbelief": None,
                "plausibility": None,
                "unknown": None,
                "conflict": None,
                "alarm_eligible": False,
                "status": "rule_only",
                "available_channels": ["video_rule"],
                "missing_channels": ["pose", "audio", "ds_fusion"],
                "updated_at": now,
            },
            {
                "scene": "fight",
                "score": None,
                "belief": None,
                "disbelief": None,
                "plausibility": None,
                "unknown": None,
                "conflict": None,
                "alarm_eligible": False,
                "status": "model_not_loaded",
                "available_channels": [],
                "missing_channels": ["action_model", "audio", "ds_fusion"],
                "updated_at": now,
            },
        ],
    }


@app.get("/api/evidence/trends")
async def api_evidence_trends(
    scene: str = "all",
    window: str = "1m",
    user: User = Depends(require_api_roles("admin", "security", "teacher")),
):
    if scene not in {"all", "fire", "fall", "fight"}:
        raise HTTPException(status_code=400, detail="Invalid scene")
    if window not in {"1m", "5m", "30m"}:
        raise HTTPException(status_code=400, detail="Invalid window")
    return {
        "contract_version": API_CONTRACT_VERSION,
        "scene": scene,
        "window": window,
        "supported": False,
        "points": [],
    }


@app.get("/api/devices/summary")
async def api_devices_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_api_roles("admin", "security")),
):
    access_devices = db.query(AccessDevice).all()
    sensor_devices = db.query(SensorDevice).all()
    return {
        "contract_version": API_CONTRACT_VERSION,
        "video": video_service.status(),
        "audio": {"status": "not_connected", "model_status": "not_loaded", "last_data_at": None},
        "sensors": {
            "simulator_running": sensor_simulator.running,
            "last_error": sensor_simulator.last_error,
            "online": sum(device.status == "online" for device in sensor_devices),
            "offline": sum(device.status == "offline" for device in sensor_devices),
        },
        "access": {
            "online": sum(device.status == "online" for device in access_devices),
            "offline": sum(device.status == "offline" for device in access_devices),
        },
    }


@app.get("/api/system/diagnostics")
async def api_system_diagnostics(user: User = Depends(require_api_roles("admin", "security"))):
    return {
        "contract_version": API_CONTRACT_VERSION,
        "backend": {"status": "running", "version": app.version},
        "video": video_service.status(),
        "sensor_loop": {"running": sensor_simulator.running, "last_error": sensor_simulator.last_error},
        "websocket": {"connected_clients": websocket_manager.connection_count},
        "fusion": {"status": "not_implemented"},
        "generated_at": datetime.now().isoformat(),
    }


@app.get("/api/alarms", response_model=list[AlarmEventOut])
async def api_alarms(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    return db.query(AlarmEvent).order_by(AlarmEvent.created_at.desc()).limit(300).all()


@app.post("/api/alarms/{alarm_id}/acknowledge")
async def api_acknowledge_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_api_roles("admin", "security", "teacher")),
):
    alarm = db.get(AlarmEvent, alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    alarm.status = "handled"
    db.commit()
    return {"ok": True, "message": "事件已确认", "data": to_dict(alarm)}


@app.post("/api/start", response_model=ApiResponse)
async def api_start(user: User = Depends(require_api_roles("admin", "security"))):
    video_service.start()
    return ApiResponse(ok=True, message="Detection started", data=video_service.status())


@app.post("/api/stop", response_model=ApiResponse)
async def api_stop(user: User = Depends(require_api_roles("admin", "security"))):
    video_service.stop()
    return ApiResponse(ok=True, message="Detection stopped", data=video_service.status())


@app.post("/api/config", response_model=ApiResponse)
async def api_config(config: ConfigUpdate, user: User = Depends(require_api_roles("admin"))):
    try:
        runtime_config.update(**config.model_dump(exclude_unset=True))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid config value: {exc}") from exc
    return ApiResponse(ok=True, message="Config updated", data=runtime_config.to_dict())


@app.post("/api/demo/init")
async def api_demo_init(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    result = initialize_demo_data(db)
    return {"ok": True, "message": "演示数据初始化完成", "data": result}


@app.post("/api/demo/trigger/{alarm_type}")
async def api_demo_trigger(alarm_type: str, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    try:
        result = await trigger_demo_alarm(db, alarm_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": result}


@app.post("/api/demo/run")
async def api_demo_run(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    video_service.start()
    result = await run_demo_sequence(db)
    return {"ok": True, "message": "一键完整演示已触发", "data": result}


@app.get("/api/persons")
async def api_persons(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    return [to_dict(row) for row in db.query(Person).order_by(Person.id.desc()).all()]


@app.post("/api/persons")
async def api_create_person(payload: PersonIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    validate_person_payload(payload)
    person = Person(**payload.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return to_dict(person)


@app.put("/api/persons/{person_id}")
async def api_update_person(person_id: int, payload: PersonIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    validate_person_payload(payload)
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    for key, value in payload.model_dump().items():
        setattr(person, key, value)
    db.commit()
    return to_dict(person)


@app.get("/api/access/devices")
async def api_access_devices(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    return [to_dict(row) for row in db.query(AccessDevice).order_by(AccessDevice.id.desc()).all()]


@app.post("/api/access/simulate")
async def api_access_simulate(payload: AccessSimulateIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    ensure_allowed(payload.access_type, ALLOWED_ACCESS_TYPES, "access_type")
    ensure_allowed(payload.auth_method, ALLOWED_AUTH_METHODS, "auth_method")
    try:
        record = await simulate_access(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return access_record_dict(record)


@app.get("/api/access/records")
async def api_access_records(
    name: str | None = None,
    result: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_api_roles("admin", "security", "teacher")),
):
    query = db.query(AccessRecord).outerjoin(Person).outerjoin(AccessDevice)
    if name:
        query = query.filter(Person.name.contains(name))
    if result:
        if result not in {"allowed", "denied"}:
            raise HTTPException(status_code=400, detail="Invalid access result")
        query = query.filter(AccessRecord.result == result)
    start_dt = parse_datetime_query(start, "start")
    end_dt = parse_datetime_query(end, "end")
    if start_dt:
        query = query.filter(AccessRecord.created_at >= start_dt)
    if end_dt:
        query = query.filter(AccessRecord.created_at <= end_dt)
    return [access_record_dict(row) for row in query.order_by(AccessRecord.created_at.desc()).limit(300).all()]


@app.get("/api/visitors")
async def api_visitors(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    return [to_dict(row) for row in db.query(VisitorRecord).order_by(VisitorRecord.id.desc()).all()]


@app.post("/api/visitors")
async def api_create_visitor(payload: VisitorIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    visitor = VisitorRecord(**payload.model_dump())
    db.add(visitor)
    db.commit()
    db.refresh(visitor)
    return to_dict(visitor)


@app.post("/api/visitors/{visitor_id}/approve")
async def api_approve_visitor(visitor_id: int, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    visitor = db.get(VisitorRecord, visitor_id)
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    visitor.status = "approved"
    db.commit()
    return to_dict(visitor)


@app.post("/api/visitors/{visitor_id}/reject")
async def api_reject_visitor(visitor_id: int, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher"))):
    visitor = db.get(VisitorRecord, visitor_id)
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    visitor.status = "rejected"
    db.commit()
    return to_dict(visitor)


@app.post("/api/visitors/{visitor_id}/simulate-entry")
async def api_visitor_entry(visitor_id: int, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    try:
        record = await simulate_visitor_entry(db, visitor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return access_record_dict(record)


@app.get("/api/sensors")
async def api_sensors(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    return [to_dict(row) for row in db.query(SensorDevice).order_by(SensorDevice.id.desc()).all()]


@app.post("/api/sensors")
async def api_create_sensor(payload: SensorIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    validate_sensor_payload(payload)
    sensor = SensorDevice(**payload.model_dump())
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return to_dict(sensor)


@app.get("/api/sensor-data")
async def api_sensor_data(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    rows = db.query(SensorData).join(SensorDevice).order_by(SensorData.created_at.desc()).limit(120).all()
    return [
        {
            **to_dict(row),
            "sensor_name": row.sensor.name,
            "sensor_type": row.sensor.sensor_type,
            "threshold_value": row.sensor.threshold_value,
            "location": row.sensor.location,
        }
        for row in rows
    ]


@app.post("/api/sensors/simulate/start")
async def api_sensor_start(user: User = Depends(require_api_roles("admin", "security"))):
    sensor_simulator.start()
    return {"ok": True, "running": sensor_simulator.running}


@app.post("/api/sensors/simulate/stop")
async def api_sensor_stop(user: User = Depends(require_api_roles("admin", "security"))):
    sensor_simulator.stop()
    return {"ok": True, "running": sensor_simulator.running}


@app.post("/api/sensors/simulate/abnormal")
async def api_sensor_abnormal(sensor_type: str = "smoke", user: User = Depends(require_api_roles("admin", "security"))):
    if sensor_type not in ALLOWED_SENSOR_TYPES:
        raise HTTPException(status_code=400, detail="Invalid sensor_type")
    await sensor_simulator.generate_once(sensor_type)
    return {"ok": True, "sensor_type": sensor_type}


@app.get("/api/map-points")
async def api_map_points(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher", "viewer"))):
    latest_alarm = db.query(AlarmEvent).order_by(AlarmEvent.created_at.desc()).first()
    return {"points": [to_dict(row) for row in db.query(MapPoint).order_by(MapPoint.id).all()], "latest_alarm": to_dict(latest_alarm) if latest_alarm else None}


@app.post("/api/map-points")
async def api_create_map_point(payload: MapPointIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    validate_map_point_payload(payload)
    point = MapPoint(**payload.model_dump())
    db.add(point)
    db.commit()
    db.refresh(point)
    return to_dict(point)


@app.put("/api/map-points/{point_id}")
async def api_update_map_point(point_id: int, payload: MapPointIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    validate_map_point_payload(payload)
    point = db.get(MapPoint, point_id)
    if not point:
        raise HTTPException(status_code=404, detail="Map point not found")
    for key, value in payload.model_dump().items():
        setattr(point, key, value)
    db.commit()
    return to_dict(point)


@app.delete("/api/map-points/{point_id}")
async def api_delete_map_point(point_id: int, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security"))):
    point = db.get(MapPoint, point_id)
    if not point:
        raise HTTPException(status_code=404, detail="Map point not found")
    db.delete(point)
    db.commit()
    return {"ok": True}


@app.get("/api/dashboard/stats")
async def api_dashboard_stats(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin", "security", "teacher", "viewer"))):
    return dashboard_stats(db)


@app.get("/api/users")
async def api_users(db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin"))):
    return [public_user(row) for row in db.query(User).order_by(User.id.desc()).all()]


@app.post("/api/users")
async def api_create_user(payload: UserIn, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin"))):
    validate_user_role(payload.role)
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    row = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return public_user(row)


@app.put("/api/users/{user_id}")
async def api_update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin"))):
    row = db.get(User, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    values = payload.model_dump(exclude_unset=True)
    validate_user_role(values.get("role"))
    if user_id == user.id and values.get("is_active") is False:
        raise HTTPException(status_code=400, detail="Cannot disable current user")
    if row.role == "admin" and values.get("role") and values["role"] != "admin":
        active_admin_count = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last active admin role")
    if row.role == "admin" and values.get("is_active") is False:
        active_admin_count = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot disable the last active admin")
    if values.get("password"):
        row.password_hash = hash_password(values.pop("password"))
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    return public_user(row)


@app.delete("/api/users/{user_id}")
async def api_delete_user(user_id: int, db: Session = Depends(get_db), user: User = Depends(require_api_roles("admin"))):
    row = db.get(User, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete current user")
    if row.role == "admin":
        active_admin_count = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last active admin")
    db.delete(row)
    db.commit()
    return {"ok": True}


@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket):
    if not get_websocket_user(websocket):
        await websocket.close(code=1008)
        return
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)


def to_dict(row) -> dict:
    data = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        data[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return data


def public_user(row: User) -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "role": row.role,
        "display_name": row.display_name,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat(),
    }


def access_record_dict(row: AccessRecord) -> dict:
    return {
        **to_dict(row),
        "person_name": row.person.name if row.person else "",
        "device_name": row.device.name if row.device else "",
        "device_location": row.device.location if row.device else "",
    }
