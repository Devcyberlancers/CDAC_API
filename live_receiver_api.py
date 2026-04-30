#!/usr/bin/env python3
import asyncio
import copy
import json
import os
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request
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
USE_SAMPLE_DATA = env_bool("USE_SAMPLE_DATA", True)
SAMPLE_REFRESH_SECONDS = env_int("SAMPLE_REFRESH_SECONDS", 3)
APP_VERSION = "2026-04-30-timed-sample"


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
    "source": None,
}

SAMPLE_PAYLOAD: Dict[str, Any] = {
    "tank": {
        "name": "main",
        "level": 72.5,
        "motor": False,
        "rain": False,
    },
    "fields": {
        "f1": {
            "water_level": 2.4,
            "moisture": 100.0,
            "ph": 7.38,
            "irrigation": True,
        },
        "f2": {
            "water_level": 5.0,
            "moisture": 100.0,
            "ph": 7.38,
            "irrigation": True,
        },
        "f3": {
            "water_level": 4.2,
            "moisture": 98.0,
            "ph": 7.21,
            "irrigation": False,
        },
        "f4": {
            "water_level": 3.7,
            "moisture": 95.0,
            "ph": 7.12,
            "irrigation": True,
        },
    },
    "npk": {
        "type": "nob",
        "field": "f2",
        "ts": 1772200983554,
        "data": {
            "N": 22,
            "P": 0,
            "K": 55,
        },
    },
}


def set_latest(obj: dict, peer: str, source: str = "live"):
    LATEST["ok"] = True
    LATEST["last"] = obj
    LATEST["received_at"] = datetime.utcnow().isoformat() + "Z"
    LATEST["received_at_ms"] = now_ms()
    LATEST["peer"] = peer
    LATEST["error"] = None
    LATEST["source"] = source
    LATEST["count"] += 1


def ensure_sample_data():
    if USE_SAMPLE_DATA and (not LATEST["ok"] or LATEST["last"] is None):
        set_latest(build_sample_payload(0), "built-in-sample", source="sample")


def build_sample_payload(step: int) -> Dict[str, Any]:
    payload = copy.deepcopy(SAMPLE_PAYLOAD)
    payload["tank"]["level"] = round(72.5 + ((step % 7) - 3) * 1.2, 2)
    payload["tank"]["motor"] = step % 2 == 0
    payload["tank"]["rain"] = step % 3 == 0

    for index, field_name in enumerate(sorted(payload["fields"].keys()), start=1):
        field = payload["fields"][field_name]
        field["water_level"] = round(field["water_level"] + ((step + index) % 5) * 0.4, 2)
        field["moisture"] = round(max(65.0, 100.0 - ((step + index) % 6) * 3.5), 2)
        field["ph"] = round(7.0 + (((step + index) % 5) - 2) * 0.08, 2)
        field["irrigation"] = (step + index) % 2 == 0

    payload["npk"]["ts"] = now_ms()
    payload["npk"]["data"]["N"] = 20 + (step % 6)
    payload["npk"]["data"]["P"] = step % 4
    payload["npk"]["data"]["K"] = 50 + ((step * 3) % 10)
    return payload


def refresh_sample_data():
    if LATEST["source"] != "sample":
        return

    last_ms = LATEST["received_at_ms"]
    if last_ms is None:
        set_latest(build_sample_payload(LATEST["count"]), "built-in-sample", source="sample")
        return

    if now_ms() - last_ms >= SAMPLE_REFRESH_SECONDS * 1000:
        set_latest(build_sample_payload(LATEST["count"]), "built-in-sample", source="sample")


def request_peer(request: Request) -> str:
    client = request.client
    if client is None:
        return "local-api"
    return f"{client.host}:{client.port}"


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
app = FastAPI(title="Live Data API")


def empty_state_response() -> Dict[str, Any]:
    return {
        "ok": False,
        "last": {},
        "message": "no live data received yet",
        "received_at": None,
        "peer": None,
        "received_count": LATEST["count"],
        "source": None,
    }


def empty_water_response() -> Dict[str, Any]:
    return {
        "ok": False,
        "tank": {},
        "fields": {},
        "message": "no live data received yet",
        "received_at": None,
        "peer": None,
        "received_count": LATEST["count"],
        "source": None,
    }

@app.get("/health")
def health():
    refresh_sample_data()
    age_ms = None
    if LATEST["received_at_ms"] is not None:
        age_ms = now_ms() - LATEST["received_at_ms"]

    return JSONResponse({
        "ok": True,
        "service": "live-receiver-api",
        "version": APP_VERSION,
        "api_listen": f"{API_HOST}:{API_PORT}",
        "sample_refresh_seconds": SAMPLE_REFRESH_SECONDS,
        "has_live_data": LATEST["source"] == "live",
        "has_sample_data": LATEST["source"] == "sample",
        "data_source": LATEST["source"],
        "received_count": LATEST["count"],
        "last_age_ms": age_ms,
        "peer": LATEST["peer"],
        "error": LATEST["error"],
    })


@app.post("/ingest")
async def ingest(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse(
            {"ok": False, "message": "payload must be a JSON object"},
            status_code=400,
        )

    set_latest(payload, request_peer(request), source="live")
    return JSONResponse({
        "ok": True,
        "message": "payload accepted",
        "received_count": LATEST["count"],
    })


@app.get("/state")
def state():
    refresh_sample_data()
    # returns the last JSON received from the data source
    if not LATEST["ok"] or LATEST["last"] is None:
        return JSONResponse(empty_state_response())

    return JSONResponse(LATEST["last"])


@app.get("/water")
def water():
    refresh_sample_data()
    if not LATEST["ok"] or LATEST["last"] is None:
        return JSONResponse(empty_water_response())

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
        "source": LATEST["source"],
    })


@app.get("/meta")
def meta():
    refresh_sample_data()
    return JSONResponse(LATEST)


async def main():
    ensure_sample_data()
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
