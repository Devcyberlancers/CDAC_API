#!/usr/bin/env python3
import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn


# -----------------------------
# CONFIG
# -----------------------------
def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


TCP_LISTEN_HOST = env_str("TCP_LISTEN_HOST", "0.0.0.0")
TCP_LISTEN_PORT = env_int("TCP_LISTEN_PORT", 42321)

API_HOST = env_str("API_HOST", "127.0.0.1")
API_PORT = env_int("API_PORT", 18081)
# For LAN access, set API_HOST=0.0.0.0 and open the firewall.

ACK = env_bool("ACK", True)


def now_ms() -> int:
    return int(time.time() * 1000)


LATEST: Dict[str, Any] = {
    "ok": False,
    "last": None,
    "received_at": None,
    "received_at_ms": None,
    "peer": None,
    "error": None,
    "count": 0,
}


def set_latest(obj: dict, peer: str):
    LATEST["ok"] = True
    LATEST["last"] = obj
    LATEST["received_at"] = datetime.utcnow().isoformat() + "Z"
    LATEST["received_at_ms"] = now_ms()
    LATEST["peer"] = peer
    LATEST["error"] = None
    LATEST["count"] += 1


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    peer_s = f"{peer[0]}:{peer[1]}" if peer else "unknown"
    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            s = line.decode("utf-8", errors="ignore").strip()
            if not s:
                continue

            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    set_latest(obj, peer_s)
                else:
                    set_latest({"_value": obj}, peer_s)
            except Exception as e:
                # keep last good state, just note error
                LATEST["error"] = f"Bad JSON from {peer_s}: {e}"

            if ACK:
                writer.write(b"OK\n")
                await writer.drain()

    except Exception as e:
        LATEST["error"] = f"TCP error from {peer_s}: {e}"
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI(title="HPC Live Receiver API")

@app.get("/health")
def health():
    age_ms = None
    if LATEST["received_at_ms"] is not None:
        age_ms = now_ms() - LATEST["received_at_ms"]

    return JSONResponse({
        "ok": True,
        "tcp_listen": f"{TCP_LISTEN_HOST}:{TCP_LISTEN_PORT}",
        "api_listen": f"{API_HOST}:{API_PORT}",
        "received_count": LATEST["count"],
        "last_age_ms": age_ms,
        "peer": LATEST["peer"],
        "error": LATEST["error"],
    })


@app.get("/state")
def state():
    # returns the last JSON received from the Raspberry Pi
    if not LATEST["ok"] or LATEST["last"] is None:
        return JSONResponse({"ok": False, "reason": "no data received yet"}, status_code=503)

    return JSONResponse(LATEST["last"])


@app.get("/water")
def water():
    if not LATEST["ok"] or LATEST["last"] is None:
        return JSONResponse({"ok": False, "reason": "no data received yet"}, status_code=503)

    latest = LATEST["last"]
    tank = latest.get("tank")
    fields = latest.get("fields", {})
    field_levels = {}

    if isinstance(fields, dict):
        for name, value in fields.items():
            if isinstance(value, dict):
                field_levels[name] = {
                    "water_level": value.get("water_level"),
                    "moisture": value.get("moisture"),
                    "irrigation": value.get("irrigation"),
                }

    return JSONResponse({
        "ok": True,
        "tank": tank,
        "fields": field_levels,
        "received_at": LATEST["received_at"],
        "peer": LATEST["peer"],
        "received_count": LATEST["count"],
    })


@app.get("/meta")
def meta():
    return JSONResponse(LATEST)


async def main():
    # Bind the TCP receiver before starting the API so startup fails cleanly.
    tcp_server = await asyncio.start_server(handle_client, TCP_LISTEN_HOST, TCP_LISTEN_PORT)
    tcp_task = asyncio.create_task(tcp_server.serve_forever())
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        tcp_task.cancel()
        tcp_server.close()
        try:
            await tcp_task
        except asyncio.CancelledError:
            pass
        await tcp_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
