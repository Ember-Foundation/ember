# Deployment

---

## Production Checklist

```bash
# 1. Install all extras
pip install "ember-api[all]"

# 2. Build Cython extensions
ember build

# 3. Verify compiled modules loaded
python -c "import ember.protocol.cprotocol; print('Cython OK')"

# 4. Start with all CPU cores
ember start --workers $(nproc) --port 8000
```

---

## Systemd Service

Create `/etc/systemd/system/myapp.service`:

```ini
[Unit]
Description=My Ember API
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/.venv/bin/ember start --workers 4 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable myapp
sudo systemctl start myapp
sudo journalctl -fu myapp
```

---

## Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install build deps for Cython
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir "ember-api[all]" cython

# Copy source and build Cython extensions
COPY . .
RUN ember build

EXPOSE 8000
CMD ["ember", "start", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t myapp .
docker run -p 8000:8000 myapp
```

---

## Nginx Reverse Proxy

Use Nginx for TLS termination, static files, and connection limiting. Route API requests to Ember:

```nginx
upstream ember {
    server 127.0.0.1:8000;
    keepalive 64;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/certs/api.crt;
    ssl_certificate_key /etc/ssl/private/api.key;

    location / {
        proxy_pass         http://ember;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE — disable buffering
        proxy_buffering       off;
        proxy_cache           off;
        proxy_read_timeout    3600s;
    }
}
```

---

## Environment Variables

Never hardcode secrets. Read them in your app:

```python
import os
from ember import Ember, ServerLimits

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL    = os.environ.get("REDIS_URL", "redis://localhost:6379")
API_KEY      = os.environ["API_KEY"]

app = Ember()
```

With systemd, set them in the service file:

```ini
[Service]
Environment=DATABASE_URL=postgresql://user:pass@localhost/mydb
Environment=REDIS_URL=redis://localhost:6379
EnvironmentFile=/opt/myapp/.env
```

---

## Worker Count Guidelines

| Server | CPU Cores | Recommended `--workers` |
|--------|-----------|------------------------|
| Dev / VPS (1–2 cores) | 1–2 | 2–4 |
| Small (4 cores) | 4 | 6 |
| Medium (8 cores) | 8 | 10 |
| Large (16+ cores) | 16+ | `nproc` |

Each worker is an independent process — if one dies, the necromancer auto-revives it.

Disable necromancer (not recommended for production):

```python
app.run(workers=4, necromancer=False)
```

---

## Health Check Endpoint

Always expose a `/health` endpoint behind `StaticCache` for load balancer probes:

```python
from ember import StaticCache

@app.get("/health", cache=StaticCache())
async def health():
    return {"status": "ok"}
```

The `StaticCache` ensures health check probes never touch the event loop after the first request — zero CPU overhead at scale.

---

## Graceful Shutdown

On `SIGTERM` (sent by systemd on `stop`), Ember:
1. Stops accepting new connections
2. Waits up to 10 s for in-flight requests to finish
3. Closes all keep-alive connections
4. Runs `BEFORE_SERVER_STOP` hooks (disconnect DB, flush queues)
5. Exits cleanly

Your `BEFORE_SERVER_STOP` hook is the right place to close DB pools:

```python
@app.hook(Events.BEFORE_SERVER_STOP)
async def shutdown(components):
    await db_pool.close()
    await redis_client.aclose()
```
