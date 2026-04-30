# HPC Integration Documentation

## Agriculture Digital Twin - Raspberry Pi to HPC Architecture

## 1. Introduction

This document describes the architecture, deployment, and operational workflow of the Real-Time Agriculture Digital Twin System, where:

- IoT sensor data is generated at the edge using ESP32 and Raspberry Pi.
- Data is aggregated on the Raspberry Pi and pushed to an HPC Virtual Machine.
- The HPC side consumes live data for analytics and simulation using Python.
- No persistent storage is required; only the latest live state is kept in memory and exposed through a live API.

This integration enables real-time monitoring, modeling, and AI-driven analysis using High Performance Computing (HPC).

The same receiver can also be deployed on a laptop or desktop system for development, demo, or non-HPC runtime use. Supported deployment targets are:

- HPC Virtual Machine
- Linux laptop or desktop
- Windows laptop or desktop

## 2. System Overview

### Architecture Flow

```text
ESP32 Sensors
  ->
MQTT (ESP32 -> Node-RED on Raspberry Pi)
  ->
Raspberry Pi Aggregator (converts MQTT topics -> "Unity-like" JSON state)
  ->
TCP Push (Raspberry Pi -> HPC VM on Port 42321)
  ->
HPC Live Receiver (in-memory latest state)
  ->
Local API on HPC (127.0.0.1:18081)
  ->
HPC Python Analysis / Simulation scripts consume API (/state)
```

### HPC Live Receiver Architecture

#### Component 1 - TCP Receiver

- Listens on `0.0.0.0:42321`
- Receives NDJSON from Raspberry Pi
- Updates in-memory state
- Does not write to disk

#### Component 2 - Local API

- Runs on `127.0.0.1:18081`
- Exposes the following endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/health` | System health status |
| `/state` | Latest live JSON state |
| `/water` | Water-focused live summary for quick validation |

## 3. Raspberry Pi Setup (Files + Services)

### 3.1 What Runs on Raspberry Pi

On the Raspberry Pi, the main component is:

- `ws-aggregator` (FastAPI + MQTT subscriber + TCP push client)

It performs the following functions:

- Subscribes to MQTT topics published from Node-RED and ESP32
- Builds the unified JSON format containing tank status, fields `f1` to `f4` with `moisture`, `ph`, and `water_level`, and the `npk` sensor block
- Pushes the unified JSON to the HPC VM on TCP port `42321`
- Optionally exposes a local API on the Pi if needed

### 3.2 Raspberry Pi Project Path

Folder:

```text
/opt/ws_aggregator/
```

Main Python file on Raspberry Pi:

```text
/opt/ws_aggregator/app.py
```

Python virtual environment on Raspberry Pi:

```text
/opt/ws_aggregator/.venv/
```

### 3.3 Raspberry Pi systemd Service

Service name on Raspberry Pi:

```text
ws-aggregator.service
```

Service file path on Raspberry Pi:

```text
/etc/systemd/system/ws-aggregator.service
```

`ExecStart` on Raspberry Pi:

```text
/opt/ws_aggregator/.venv/bin/python /opt/ws_aggregator/app.py
```

Purpose:

- Keeps the Pi aggregator always running
- Auto-restarts on failure
- Pushes live data to HPC continuously

Service commands on Raspberry Pi:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ws-aggregator
sudo systemctl status ws-aggregator --no-pager
sudo journalctl -u ws-aggregator -f
```

## 4. Data Model (Unified Payload)

The system transmits JSON payload in a Unity-like state format.

### Example Payload

```json
{
  "ok": true,
  "last": {
    "tank": {
      "name": "main",
      "level": 72.5,
      "motor": false,
      "rain": false
    },
    "fields": {
      "f1": {
        "water_level": 2.4,
        "moisture": 100.0,
        "ph": 7.38,
        "irrigation": true,
        "drain": false,
        "acid": false,
        "base": false
      },
      "f2": {
        "water_level": 5.0,
        "moisture": 100.0,
        "ph": 7.38,
        "irrigation": true,
        "drain": false,
        "acid": false,
        "base": false
      },
      "f3": {
        "water_level": 5.0,
        "moisture": 100.0,
        "ph": 7.38,
        "irrigation": true,
        "drain": false,
        "acid": false,
        "base": false
      },
      "f4": {
        "water_level": 5.0,
        "moisture": 100.0,
        "ph": 7.38,
        "irrigation": true,
        "drain": false,
        "acid": false,
        "base": false
      }
    },
    "npk": {
      "type": "nob",
      "field": "f2",
      "ts": 1772200983554,
      "data": {
        "N": 22,
        "P": 0,
        "K": 55,
        "T": 11,
        "H": 0,
        "PH": 0,
        "R": 0
      }
    }
  }
}
```

## 5. HPC Setup (Files + Services)

### 5.1 What Runs on HPC

On HPC, the main component is:

- HPC Live Receiver + API

It performs the following:

- Receives TCP pushes on port `42321`
- Maintains the latest state in RAM
- Exposes a local-only API for scripts on `http://127.0.0.1:18081`
- Provides `http://127.0.0.1:18081/health`
- Provides `http://127.0.0.1:18081/state`

This ensures live access without requiring disk storage.

### 5.2 HPC Project Path

Folder:

```text
/home/chuk/pi_receiver/
```

Main Python file on HPC:

```text
/home/chuk/pi_receiver/live_receiver_api.py
```

### 5.3 HPC systemd Service

Service name on HPC:

```text
pi-live-api.service
```

Service file path on HPC:

```text
/etc/systemd/system/pi-live-api.service
```

`ExecStart` on HPC:

```text
/usr/bin/python3 /home/chuk/pi_receiver/live_receiver_api.py
```

Function:

- Keeps the HPC receiver always running
- Auto-restarts on reboot or failure
- Makes live data available to HPC scripts via HTTP

Service commands on HPC:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pi-live-api
sudo systemctl status pi-live-api --no-pager
sudo journalctl -u pi-live-api -f
```

## 6. Deploying on Linux Laptop or Desktop

The same receiver can be deployed on a Linux workstation, laptop, or desktop for testing or production-style use outside the HPC environment.

### 6.1 Linux Requirements

- Python `3.10+`
- Network access from the Raspberry Pi to the Linux machine on TCP port `42321`
- Firewall rule allowing inbound TCP `42321` if the Pi is on a different machine

### 6.2 Linux Project Location

Example folder:

```text
/home/<user>/pi_receiver/
```

### 6.3 Linux Installation

```bash
cd /home/<user>/pi_receiver
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 6.4 Linux Runtime Configuration

Default behavior:

- TCP receiver listens on `0.0.0.0:42321`
- API listens on `127.0.0.1:18081`

Optional environment variables:

- `TCP_LISTEN_HOST`
- `TCP_LISTEN_PORT`
- `API_HOST`
- `API_PORT`
- `ACK`

Example:

```bash
export TCP_LISTEN_HOST=0.0.0.0
export TCP_LISTEN_PORT=42321
export API_HOST=127.0.0.1
export API_PORT=18081
export ACK=true
```

If other machines must access the HTTP API, set:

```bash
export API_HOST=0.0.0.0
```

### 6.5 Linux Run Command

```bash
cd /home/<user>/pi_receiver
source .venv/bin/activate
python live_receiver_api.py
```

### 6.6 Linux systemd Service

Example service file:

```ini
[Unit]
Description=Pi Live Receiver API
After=network.target

[Service]
Type=simple
User=<user>
WorkingDirectory=/home/<user>/pi_receiver
Environment=TCP_LISTEN_HOST=0.0.0.0
Environment=TCP_LISTEN_PORT=42321
Environment=API_HOST=127.0.0.1
Environment=API_PORT=18081
ExecStart=/home/<user>/pi_receiver/.venv/bin/python /home/<user>/pi_receiver/live_receiver_api.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save as:

```text
/etc/systemd/system/pi-live-api.service
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pi-live-api
sudo systemctl status pi-live-api --no-pager
```

## 7. Deploying on Windows Laptop or Desktop

The receiver also runs on Windows for demos, lab systems, or developer workstations.

### 7.1 Windows Requirements

- Windows 10 or Windows 11
- Python `3.10+`
- PowerShell or Command Prompt
- Firewall rule allowing inbound TCP `42321` if Raspberry Pi pushes from another machine

### 7.2 Windows Project Location

Example folder:

```text
C:\pi_receiver\
```

### 7.3 Windows Installation

PowerShell:

```powershell
cd C:\pi_receiver
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 7.4 Windows Runtime Configuration

PowerShell:

```powershell
$env:TCP_LISTEN_HOST = "0.0.0.0"
$env:TCP_LISTEN_PORT = "42321"
$env:API_HOST = "127.0.0.1"
$env:API_PORT = "18081"
$env:ACK = "true"
```

If the HTTP API should be reachable from other machines:

```powershell
$env:API_HOST = "0.0.0.0"
```

### 7.5 Windows Run Command

PowerShell:

```powershell
cd C:\pi_receiver
.\.venv\Scripts\Activate.ps1
python .\live_receiver_api.py
```

### 7.6 Windows Startup Options

Recommended options:

- Use Windows Task Scheduler to start the receiver at boot or user logon
- Use NSSM if a Windows service wrapper is preferred

Example Task Scheduler action:

```text
Program/script:
C:\pi_receiver\.venv\Scripts\python.exe

Add arguments:
C:\pi_receiver\live_receiver_api.py

Start in:
C:\pi_receiver
```

### 7.7 Windows Firewall

If Raspberry Pi is pushing data into the Windows machine, allow inbound TCP `42321`.

PowerShell example:

```powershell
New-NetFirewallRule -DisplayName "Pi Live Receiver TCP 42321" -Direction Inbound -Protocol TCP -LocalPort 42321 -Action Allow
```

If remote access to the HTTP API is needed, also allow TCP `18081`.

## 8. Live API Endpoints

### `/health`

Returns receiver status, including:

- whether the receiver is active
- age of the last received message
- peer IP sending data
- total received message count

### `/state`

Returns the latest live JSON state from memory:

```bash
curl http://127.0.0.1:18081/state
```

### `/water`

Returns a compact water-focused snapshot derived from the latest state. This is useful for quick verification of tank level and field water levels.

### `/meta`

Returns internal in-memory metadata such as timestamps, counters, last peer, and latest error state.

## 9. Verification Steps

### 9.1 On Linux or HPC (Ports)

Check that the receiver is listening:

```bash
sudo ss -lntp | egrep '42321|18081'
```

### 9.2 On Linux, HPC, or WSL (API)

```bash
curl http://127.0.0.1:18081/water
curl http://127.0.0.1:18081/state
curl http://127.0.0.1:18081/health
curl http://127.0.0.1:18081/meta
```

### 9.3 On Windows PowerShell (API)

```powershell
Invoke-RestMethod http://127.0.0.1:18081/water
Invoke-RestMethod http://127.0.0.1:18081/state
Invoke-RestMethod http://127.0.0.1:18081/health
Invoke-RestMethod http://127.0.0.1:18081/meta
```

### 9.4 On Raspberry Pi (Push Connectivity)

```bash
nc -vz paramutkarsh.cdacb.in 42321
```

### 9.5 Local Functional Test

Start the receiver and send one NDJSON sample line:

```bash
printf '%s\n' '{"tank":{"name":"main","level":67.0},"fields":{"f1":{"water_level":9.0,"moisture":81.0,"irrigation":true}}}' | nc 127.0.0.1 42321
```

Then verify:

```bash
curl http://127.0.0.1:18081/state
curl http://127.0.0.1:18081/water
```

## 10. Final Clean State

Only these services remain active:

- Raspberry Pi: `ws-aggregator.service`
- HPC VM: `pi-live-api.service`

For Linux laptop or desktop deployment, the same service name `pi-live-api.service` can be used.

For Windows deployment, startup should be handled using Task Scheduler or an equivalent service wrapper.
