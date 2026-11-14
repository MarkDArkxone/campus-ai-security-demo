import os
import socket

import uvicorn


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def choose_port(host: str, preferred_port: int) -> int:
    if port_is_free(host, preferred_port):
        return preferred_port
    for port in range(preferred_port + 1, preferred_port + 20):
        if port_is_free(host, port):
            print(f"Port {preferred_port} is already in use. Using http://{host}:{port} instead.")
            return port
    raise RuntimeError(f"No available port found near {preferred_port}. Please close another running server.")


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    try:
        preferred_port = int(os.getenv("PORT", "8000"))
    except ValueError:
        print("Invalid PORT environment variable. Falling back to 8000.")
        preferred_port = 8000
    port = choose_port(host, preferred_port)
    print(f"Campus AI Security Demo is starting at http://{host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "0") == "1",
    )
