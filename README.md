# Live Data API

This project exposes live sensor data through a local HTTP API.

The main requirement is simple:

- client applications should read data using the API
- the API should work locally on a laptop or desktop
- the API should still respond cleanly even when no live data has arrived yet

## Local API

Default base URL:

```text
http://127.0.0.1:18081
```

Available endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/health` | API status |
| `/ingest` | Submit a JSON payload directly to the API |
| `/state` | Latest full JSON payload |
| `/water` | Water-focused view of the latest payload |
| `/meta` | Internal metadata such as timestamps and counters |

## Behavior When No Data Is Available

The API continues to work even if no live data has been received yet.

In that case:

- `/health` returns API status with `has_live_data: false`
- `/state` returns an empty default response
- `/water` returns an empty default response

Example `GET /state` response before data arrives:

```json
{
  "ok": false,
  "last": {},
  "message": "no live data received yet",
  "received_at": null,
  "peer": null,
  "received_count": 0
}
```

Example `GET /water` response before data arrives:

```json
{
  "ok": false,
  "tank": {},
  "fields": {},
  "message": "no live data received yet",
  "received_at": null,
  "peer": null,
  "received_count": 0
}
```

## Example Responses After Data Arrives

Example `GET /state` response:

```json
{
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
      "irrigation": true
    },
    "f2": {
      "water_level": 5.0,
      "moisture": 100.0,
      "ph": 7.38,
      "irrigation": true
    }
  },
  "npk": {
    "type": "nob",
    "field": "f2",
    "ts": 1772200983554,
    "data": {
      "N": 22,
      "P": 0,
      "K": 55
    }
  }
}
```

Example `GET /water` response:

```json
{
  "ok": true,
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
      "irrigation": true
    },
    "f2": {
      "water_level": 5.0,
      "moisture": 100.0,
      "irrigation": true
    }
  },
  "received_at": "2026-04-30T12:00:00Z",
  "peer": "127.0.0.1:50000",
  "received_count": 12
}
```

## Local Data Injection

If you are testing on a local machine and no external device is pushing data yet, send data directly to the API:

```bash
curl -X POST http://127.0.0.1:18081/ingest \
  -H "Content-Type: application/json" \
  -d '{"tank":{"name":"main","level":72.5,"motor":false,"rain":false},"fields":{"f1":{"water_level":2.4,"moisture":100.0,"ph":7.38,"irrigation":true},"f2":{"water_level":5.0,"moisture":100.0,"ph":7.38,"irrigation":true}}}'
```

Then read it back:

```bash
curl http://127.0.0.1:18081/state
curl http://127.0.0.1:18081/water
```

## Run Locally On Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python live_receiver_api.py
```

## Run Locally On Windows

PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python .\live_receiver_api.py
```

## Local API Checks

Linux:

```bash
curl http://127.0.0.1:18081/health
curl -X POST http://127.0.0.1:18081/ingest -H "Content-Type: application/json" -d '{"tank":{"name":"main","level":72.5}}'
curl http://127.0.0.1:18081/state
curl http://127.0.0.1:18081/water
curl http://127.0.0.1:18081/meta
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:18081/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18081/ingest -ContentType "application/json" -Body '{"tank":{"name":"main","level":72.5}}'
Invoke-RestMethod http://127.0.0.1:18081/state
Invoke-RestMethod http://127.0.0.1:18081/water
Invoke-RestMethod http://127.0.0.1:18081/meta
```

## Notes

- The API is intended to be consumed locally by applications, scripts, or dashboards.
- The latest received payload is kept in memory.
- The API remains available even before the first live message arrives.
