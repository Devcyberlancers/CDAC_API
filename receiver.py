#!/usr/bin/env python3
import asyncio
import json
import os
from datetime import datetime


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


LISTEN_HOST = env_str("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = env_int("LISTEN_PORT", 42321)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    print(f"[+] Connected: {peer}", flush=True)

    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            s = line.decode("utf-8", errors="ignore").strip()
            if not s:
                continue

            # validate/normalize JSON
            try:
                obj = json.loads(s)
                obj["_received_at"] = datetime.utcnow().isoformat() + "Z"
                print(json.dumps(obj, separators=(",", ":")), flush=True)
            except Exception:
                print(json.dumps({"_raw": s, "_received_at": datetime.utcnow().isoformat() + "Z"}), flush=True)

            # optional ACK
            writer.write(b"OK\n")
            await writer.drain()

    except Exception as e:
        print(f"[!] Error with {peer}: {e}", flush=True)
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"[-] Disconnected: {peer}", flush=True)

async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"[*] Listening on {addrs}", flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
