# Pi Receiver API

Small local receiver service for Raspberry Pi sensor/state data.

It provides:

- A raw TCP receiver that accepts newline-delimited JSON messages.
- A FastAPI service that keeps the latest payload in memory.
- Simple endpoints for health checks and reading the latest received state.

## Files

- `live_receiver_api.py`: starts the TCP receiver and the HTTP API together.
- `receiver.py`: TCP-only receiver that prints normalized JSON to stdout.
- `requirements.txt`: Python dependencies for the API service.
- `.env.example`: optional environment variables for local deployment.

## API Endpoints

When `live_receiver_api.py` is running:

- `GET /health`: receiver status, message count, last message age, last peer, error state.
- `GET /state`: latest JSON payload received from the Raspberry Pi.
- `GET /meta`: internal in-memory state including timestamps and counters.

Default HTTP bind:

- `127.0.0.1:18080`

Default TCP bind:

- `0.0.0.0:42321`

## Local Setup

### 1. Clone or copy the project

```bash
git clone <your-github-repo-url>
cd pi_receiver
```

If you are copying it directly to another machine without GitHub:

```bash
scp -r pi_receiver user@target-host:/path/to/projects/
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Optional configuration

```bash
cp .env.example .env
set -a
source .env
set +a
```

The scripts read these environment variables from the shell environment:

- `TCP_LISTEN_HOST`
- `TCP_LISTEN_PORT`
- `API_HOST`
- `API_PORT`
- `ACK`

`receiver.py` also supports:

- `LISTEN_HOST`
- `LISTEN_PORT`

Example:

```bash
export API_HOST=0.0.0.0
export API_PORT=18080
export TCP_LISTEN_PORT=42321
```

## Run The API

```bash
source .venv/bin/activate
python live_receiver_api.py
```

This starts:

- the TCP receiver on `TCP_LISTEN_HOST:TCP_LISTEN_PORT`
- the HTTP API on `API_HOST:API_PORT`

## Run TCP-Only Receiver

```bash
python receiver.py
```

This version prints each valid JSON message to stdout with a `_received_at` timestamp and returns `OK` for each received line.

## Test Locally

Start the API in one terminal:

```bash
python live_receiver_api.py
```

Send a sample JSON line from another terminal:

```bash
printf '%s\n' '{"tank":{"name":"main","level":67.0},"fields":{"f1":{"water_level":9.0}}}' | nc 127.0.0.1 42321
```

Check the HTTP API:

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/state
curl http://127.0.0.1:18080/meta
```

## Deploy On Another Local System

For a machine on the same network:

1. Install Python 3.9+.
2. Copy or clone this repository.
3. Create the virtual environment and install `requirements.txt`.
4. Set `API_HOST=0.0.0.0` if other machines must access the HTTP API.
5. Open the firewall for the API port and TCP ingest port if needed.
6. Start `python live_receiver_api.py`.

If the Raspberry Pi sends data to this host, point the Pi client to:

- TCP host: IP address of the machine running this project
- TCP port: `42321` or your configured `TCP_LISTEN_PORT`

## Push To GitHub

From inside `pi_receiver`, run:

```bash
git add .
git commit -m "Initial commit: Pi receiver API"
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Notes

- The latest state is kept only in memory by `live_receiver_api.py`.
- `pi_state.ndjson` looks like captured runtime data, so `*.ndjson` is excluded from Git by default.
- If you want persisted history, add file or database storage separately.
