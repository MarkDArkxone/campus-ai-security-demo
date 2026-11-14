# 基于深度学习的校园智能安防系统 Demo

## 快速启动

```bash
pip install -r requirements.txt
python run.py
```

访问：

```text
http://127.0.0.1:8000
```

默认账号：

```text
admin / <CAMPUS_ADMIN_PASSWORD>
```

Windows 也可以直接双击：

```text
install.bat
start.bat
```

这是一个本地可运行的校园智能安防 MVP，适合课程设计、创新项目和答辩演示。系统基于 FastAPI + OpenCV + YOLOv8 + SQLite + Jinja2 + 原生 HTML/CSS/JS，实现视频检测、告警中心、门禁管理、传感器模拟、校园地图、权限控制和数字孪生态势大屏。

## 默认账号

```text
username: admin
password: <CAMPUS_ADMIN_PASSWORD>
role: admin
```

访问后台页面前需要先登录：

```text
http://127.0.0.1:8000/login
```

## 功能列表

- YOLOv8 人员检测、电子围栏、人员聚集、疑似跌倒告警
- 视频烟火识别：有自定义模型时使用 YOLO；没有模型时使用 OpenCV 颜色规则 Demo
- 告警写入 SQLite，并保存截图到 `app/static/snapshots/`
- WebSocket 实时推送告警到监控页、地图页和大屏页
- 门禁管理：人员、设备、出入记录、访客预约和模拟通行
- 黑名单人员模拟通行会生成 `access_denied` 告警
- 传感器接入：烟雾、温度、电流、电压、湿度设备和模拟数据
- 传感器阈值异常会生成 `smoke_warning`、`temperature_warning`、`electricity_warning`
- 校园二维地图展示摄像头、门禁、传感器和告警点位
- 数字孪生大屏展示今日告警、高危告警、在线设备、当前人数和最新告警
- 简单权限系统：admin、security、teacher、viewer

## 安装依赖

建议使用 Python 3.11+。Windows + PyCharm 可直接打开项目目录。

```bash
cd campus_ai_security_demo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

如果你使用的是项目上一级已有的 `.venv`，也可以在项目目录运行：

```bash
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

首次启动 YOLO 检测时，Ultralytics 可能会自动下载 `yolov8n.pt`。

## 启动命令

```bash
python run.py
```

打开：

```text
http://127.0.0.1:8000
```

## 页面地址

- 登录：`/login`
- 首页：`/`
- 监控中心：`/monitor`
- 证据分析：`/analysis`（未接入的 DS 字段明确显示为 `—`）
- 报警事件：`/events`（兼容旧地址 `/alarms`）
- 设备状态：`/devices`
- 系统配置与诊断：`/settings`
- 门禁管理：`/access`
- 访客管理：`/visitors`
- 传感器：`/sensors`
- 校园地图：`/map`
- 数字孪生大屏：`/dashboard`
- 用户管理：admin 可访问 `/users`
- API 文档：`/docs`

首页提供“一键完整演示”按钮，可自动初始化演示数据、启动视频检测并触发多类模拟告警，适合答辩时快速展示闭环效果。

## 答辩演示步骤

1. 打开 `http://127.0.0.1:8000/login`，使用 `admin / <CAMPUS_ADMIN_PASSWORD>` 登录。
2. 进入首页，点击“一键初始化演示数据”。
3. 进入 `/dashboard`，展示校园安全态势大屏。
4. 回到首页或进入 `/monitor`，点击“启动视频检测”。
5. 在首页使用演示按钮触发电子围栏、人员聚集、跌倒、烟雾、温度、黑名单通行告警。
6. 打开 `/alarms`，展示告警写入数据库、截图路径和历史记录。
7. 打开 `/map`，展示点位变红或闪烁。
8. 打开 `/access`，演示黑名单人员模拟通行。
9. 打开 `/sensors`，演示传感器模拟数据和异常数据。

## 项目创新点

- 将视频 AI 检测、门禁、传感器、地图和大屏整合为一个校园安防 MVP。
- 支持无摄像头、无模型、无硬件的完整模拟演示，降低课程答辩部署成本。
- 使用 WebSocket 实现告警实时推送，监控页、地图页和大屏同步更新。
- 使用电子围栏、人员聚集、疑似跌倒、烟火识别等多类规则构成复合告警场景。
- 在不做人脸识别的前提下，保留门禁业务闭环，规避隐私和合规复杂度。

## 技术架构说明

- 后端：FastAPI 提供页面路由、REST API、WebSocket 和 MJPEG 视频流。
- 数据层：SQLite + SQLAlchemy，启动时自动建表和初始化默认数据。
- AI 检测：Ultralytics YOLOv8 检测人员；加载失败时自动进入 mock 检测。
- 视频处理：OpenCV 读取摄像头或视频文件；摄像头不可用时生成模拟校园画面。
- 开源增强：引入 Roboflow `supervision` 作为成熟 CV 工具库，用于电子围栏 PolygonZone 判断；如果该库不可用，会自动回退到 OpenCV 规则。
- 前端：Jinja2 模板 + 原生 HTML/CSS/JS，不依赖 Vue/React。
- 实时通信：WebSocket 推送告警到监控页、地图页和数字孪生大屏。
- 前后端接入层：`app/static/js/api-client.js` 统一管理 REST、WebSocket、MJPEG 地址、超时和鉴权。

独立后端开发请阅读：[`docs/后端接入手册.md`](docs/后端接入手册.md)。前端可通过 `CAMPUS_API_BASE_URL` 和 `CAMPUS_WS_BASE_URL` 切换到新的后端实现。
- 运行依赖：`websockets` 用于 Uvicorn 的 WebSocket 支持，确保实时告警演示可用。

## 系统运行截图位置说明

- 告警截图自动保存到：`app/static/snapshots/`
- 告警中心页面中的“查看截图”链接可直接打开对应图片。
- 如果演示按钮触发的是纯模拟业务告警，可能没有截图；视频检测告警会保存当前帧截图。

## 常见问题排查

- 登录失败：确认默认账号是 `admin / <CAMPUS_ADMIN_PASSWORD>`，数据库会在启动时自动创建管理员。
- 摄像头打不开：系统会自动进入 mock 摄像头模式，`/monitor` 仍可显示模拟画面。
- YOLO 模型不可用：系统会自动进入 mock person 检测模式，不影响演示流程。
- 页面 403：当前账号角色权限不足，请使用 admin 登录。
- 端口占用：关闭已有 `python run.py` 进程，或修改 `run.py` 端口。
- 依赖安装慢：Ultralytics/PyTorch 较大，建议提前执行 `pip install -r requirements.txt`。

## 权限说明

- admin：全部权限
- security：监控、告警、门禁、传感器、地图、大屏
- teacher：部分告警、访客、地图、大屏
- viewer：地图、大屏和系统状态

未登录访问后台页面会自动跳转到 `/login`。无权限访问会显示 403 页面。

## 摄像头和本地视频

默认视频源在 `app/config.py`：

```python
VIDEO_SOURCE = 0
```

`0` 表示默认摄像头。使用本地视频时，可以放到：

```text
sample_videos/test.mp4
```

然后改为：

```python
VIDEO_SOURCE = str(BASE_DIR / "sample_videos" / "test.mp4")
```

也可以调用 `/api/config` 修改运行配置。

## 烟火识别配置

`app/config.py`：

```python
FIRE_MODEL_PATH = ""
ENABLE_FIRE_DETECTION = True
FIRE_CONF_THRESHOLD = 0.4
FIRE_ALARM_COOLDOWN_SECONDS = 15
```

如果 `FIRE_MODEL_PATH` 指向存在的 YOLO 模型文件，则使用自定义模型识别 `fire / smoke`。如果没有模型，系统会自动使用 OpenCV HSV 颜色规则做 Demo 级火焰/烟雾检测。

## 常用 API

- `GET /api/health`
- `GET /api/alarms`
- `POST /api/start`
- `POST /api/stop`
- `GET /api/persons`
- `POST /api/persons`
- `POST /api/access/simulate`
- `GET /api/access/records`
- `POST /api/visitors`
- `POST /api/visitors/{id}/approve`
- `POST /api/visitors/{id}/reject`
- `GET /api/sensors`
- `POST /api/sensors`
- `GET /api/sensor-data`
- `POST /api/sensors/simulate/start`
- `POST /api/sensors/simulate/stop`
- `POST /api/sensors/simulate/abnormal?sensor_type=smoke`
- `GET /api/map-points`
- `GET /api/dashboard/stats`
- `POST /api/demo/init`
- `POST /api/demo/run`
- `POST /api/demo/trigger/{alarm_type}`

## Demo 局限性

- 当前跌倒检测是 bbox 宽高比规则模拟，不是正式行为识别模型。
- 当前烟火识别在无专用模型时是颜色规则 Demo，可能误报或漏报。
- 不做真正人脸识别，只做人员信息和模拟门禁通行，避免隐私和合规复杂度。
- 不做真正三维数字孪生，先实现二维校园地图和科技风大屏。
- 传感器、门禁、访客入校均支持模拟模式，没有真实硬件也能演示。
- 电子围栏坐标仍为代码预设，后续可扩展为网页拖拽配置。
- 打架识别暂不实现，后续可接入 CNN+LSTM、SlowFast、VideoMAE 等视频行为识别模型。

## 后续扩展方向

- 多摄像头通道和多区域电子围栏
- 门禁设备真实协议接入
- 传感器 MQTT/串口/HTTP 接入
- 告警处置流程、工单闭环和报表导出
- 地图点位网页拖拽编辑
- 更强的姿态估计、行为识别和烟火专用模型
