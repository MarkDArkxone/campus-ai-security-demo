from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(connection)


websocket_manager = WebSocketManager()
