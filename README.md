# JustMySockets-to-ClashMi

> Just My Socks can't provide a correct format for Clash Mi — this tool transforms it.

A production-ready service that accepts a Just My Socks (or generic) proxy
subscription — Base64 blob, `ss://`, `vmess://`, `vless://`, `trojan://`,
`hysteria2://`, `tuic://`, or a mixed list — and converts it into a **fully
compatible Mihomo / Clash Meta YAML**, exposed through an HTTP endpoint that
Clash Mi (and Clash Verge / OpenClash) can subscribe to directly.

## Quick start

```bash
docker compose up -d --build
```

The service listens on `http://localhost:8000`. Subscribe in your Clash client:

```
http://<your-host>:8000/clash?url=<URL-encoded subscription URL>
```

## Endpoints

| Method | Path        | Description                                | Content-Type       |
|--------|-------------|--------------------------------------------|--------------------|
| GET    | `/`         | `Subscription Converter Running`           | `text/plain`       |
| GET    | `/health`   | JSON health + cache size                   | `application/json` |
| GET    | `/clash`    | Mihomo / Clash Meta YAML                   | `application/yaml` |
| GET    | `/surge`    | Surge config (same parser)                 | `text/plain`       |
| GET    | `/sing-box` | sing-box JSON (same parser)                | `application/json` |
| GET    | `/docs`     | OpenAPI / Swagger UI                       | `text/html`        |

All conversion endpoints take `?url=...` and an optional `&force_refresh=true`
to bypass the cache and re-download the upstream immediately.

## Dynamic updates (always fresh)

- The cache stores the **parsed upstream subscription** (nodes), not rendered
  YAML. The YAML is regenerated dynamically on every request.
- The upstream is re-downloaded automatically every `CACHE_TTL_SECONDS` (300s).
- `&force_refresh=true` forces an immediate re-download.
- `X-Subscription-Fetched-At` reports when the upstream was last fetched.
- No proxy server IP is ever hardcoded — every node comes from the upstream.

## Configuration

All settings are environment variables (see `docker-compose.yml`):

| Variable                | Default                                 | Description                          |
|-------------------------|-----------------------------------------|--------------------------------------|
| `HOST` / `PORT`         | `0.0.0.0` / `8000`                      | Bind address / port.                 |
| `WORKERS`               | `2`                                     | Uvicorn workers.                     |
| `CACHE_TTL_SECONDS`     | `300`                                   | Subscription cache TTL.              |
| `FETCH_TIMEOUT_SECONDS` | `15`                                    | Upstream fetch timeout.              |
| `TEST_URL` / `TEST_INTERVAL` | gstatic generate_204 / `300`        | url-test target for the AUTO group.  |
| `DNS_NAMESERVER` / `DNS_FALLBACK` / `DNS_BOOTSTRAP` | *(public resolvers)*     | DNS resolvers (not proxy servers).   |
| `ALLOWED_HOSTS`         | *(empty = all)*                         | Comma-separated upstream allow-list. |

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

# run all gates
ruff check subscription-converter
ruff format --check subscription-converter
mypy subscription-converter/subscription_converter
pytest
```

Python 3.12 is the runtime target; CI also tests 3.13 for forward-compat.

## Security

- Subscription URLs and passwords are **never logged** — a logging filter
  redacts any `url=...` value.
- The cache stores HMAC digests of URLs, never raw URLs.
- The container runs as a non-root user.
- Use `ALLOWED_HOSTS` to restrict which upstreams may be contacted.

## Deployment

### VPS

```bash
docker compose up -d --build
# behind Caddy (automatic HTTPS):
#   reverse_proxy 127.0.0.1:8000
```

### Railway / Render / Fly.io

Deploy from this repo; the `Dockerfile` is auto-detected. Set `PORT` if the
platform requires it (the CMD honors `$PORT`).

### Cloudflare Tunnel

Run the converter on a non-public host and expose it via Cloudflare Tunnel for
free TLS + DDoS protection:

```bash
cloudflared tunnel create converter
cloudflared tunnel route dns converter converter.yourdomain.com
cloudflared tunnel run --url http://localhost:8000 converter
```

## License

MIT.
