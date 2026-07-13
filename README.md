# JustMySockets-to-ClashMi

> Just My Socks can't provide a correct format for Clash Mi — this tool transforms it.
>
> Just My Socks 无法为 Clash Mi 提供正确的格式 —— 本工具负责转换。

[English](#english) · [中文](#中文)

---

# English

A **production-ready** service that accepts a Just My Socks (or any generic) proxy
subscription — a Base64 blob, a single `ss://` link, or a mixed list of
`ss://`, `vmess://`, `vless://`, `trojan://`, `hysteria2://`, `tuic://` links —
and converts it into a **fully compatible Mihomo / Clash Meta YAML**
configuration. The result is exposed through an HTTP endpoint that Clash Mi
(and Clash Verge, OpenClash, etc.) can subscribe to directly.

> **Why is this needed?** Just My Socks hands out a subscription in a format
> Clash Mi doesn't understand. This service downloads that subscription,
> decodes every node, and re-emits a clean Clash YAML on the fly. Your Clash
> client only ever talks to this converter — never the upstream provider.

---

## Part 1 — Quick Start

The fastest path: run it with Docker.

```bash
# 1. Clone
git clone https://github.com/JunWeiLi233/JustMySockets-to-ClashMi.git
cd JustMySockets-to-ClashMi

# 2. Build & run (one command)
docker compose up -d --build
```

The service now listens on `http://localhost:8000`.

Subscribe in your Clash client using:

```
http://<your-host>:8000/clash?url=<URL-encoded subscription URL>
```

> **Tip — what is a "URL-encoded subscription URL"?**
> Subscription URLs contain characters like `?`, `&`, `=` that break HTTP query
> strings. You must URL-encode the whole subscription URL before pasting it
> after `?url=`. For example:
> ```
> # raw
> https://jmssub.net/getsub.php?sid=1&token=abc
> # URL-encoded (paste this after ?url=)
> https%3A%2F%2Fjmssub.net%2Fgetsub.php%3Fsid%3D1%26token%3Dabc
> ```
> Many tools can do this: `python -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "<url>"`
> or any online "URL encoder".

That's it — your Clash client will now pull a valid config every time it refreshes.

---

## Part 2 — Installation (without Docker)

If you want to run it directly with Python, follow these steps in order.

### 2.1 Requirements

- **Python 3.12** or newer (3.13 also works). Check yours:
  ```bash
  python3 --version   # must be >= 3.12
  ```
- **pip** (bundled with Python).
- *(Optional)* **Git** to clone the repo.

### 2.2 Step-by-step

```bash
# 1. Get the code
git clone https://github.com/JunWeiLi233/JustMySockets-to-ClashMi.git
cd JustMySockets-to-ClashMi

# 2. Create and activate a virtual environment (keeps your system Python clean)
python3.12 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# 3. Install ALL required Python packages
pip install -r requirements.txt
```

> **What does `requirements.txt` contain?** It pins the runtime dependencies:
> `fastapi` (the web framework), `uvicorn` (the ASGI server), `httpx` (HTTP
> client used to download the upstream subscription), `pydantic` (data
> validation for proxy nodes), and `PyYAML` (to emit the Clash YAML). After
> this step you have everything needed to run the service.

```bash
# 4. Run it
uvicorn subscription_converter.app:app --host 0.0.0.0 --port 8000
```

You should see `Uvicorn running on http://0.0.0.0:8000`. Open
`http://localhost:8000/` in a browser — it should say
`Subscription Converter Running`.

### 2.3 (Optional) Development dependencies

If you plan to develop or run the test suite, also install the dev tools:

```bash
pip install -r requirements-dev.txt
```

This adds `pytest` + `pytest-asyncio` (testing), `respx` (HTTP mocking),
`ruff` (linter/formatter), `mypy` (type checker), and `pre-commit` (git hooks).

---

## Part 3 — How It Works

Understanding the pipeline helps you debug and extend the service.

```
┌──────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│  Clash client    │────▶│  /clash      │────▶│   Parser    │────▶│ Converter  │
│  (Clash Mi, ...) │◀────│  endpoint    │◀────│  (decode +  │◀────│ (Mihomo    │
│                  │     │  (FastAPI)   │     │   parse)    │     │  YAML)     │
└──────────────────┘     └──────────────┘     └─────────────┘     └────────────┘
                                │                     ▲
                                │                     │
                          ┌─────▼─────┐         ┌─────┴─────┐
                          │   Cache   │         │ Upstream  │
                          │ (5 min)   │◀────────│ sub URL   │
                          └───────────┘         └───────────┘
```

### 3.1 Parser (input side)

The parser is **provider-independent** — it doesn't care who published the
subscription. It:

1. **Downloads** the subscription body over HTTP (via `httpx`).
2. **Detects the format**: a plain list of links, a single link, or a Base64
   blob. Base64 is decoded automatically (padding/urlsafe tolerant).
3. **Parses each link** into a normalized `ProxyNode`. Supported schemes:
   - `ss://` — Shadowsocks (SIP002 + legacy; `obfs-local` → `obfs`)
   - `ssr://` — ShadowsocksR
   - `vmess://` — VMess (v2rayN JSON; ws/grpc/h2 transport)
   - `vless://` — VLESS (incl. REALITY: public-key/short-id/fingerprint/flow)
   - `trojan://` — Trojan (ws/grpc)
   - `hysteria2://` / `hy2://` — Hysteria2 (salamander obfs + bandwidth)
   - `hysteria://` — Hysteria v1
   - `tuic://` — TUIC v5
4. **Returns** a `Subscription` (the list of nodes + safe upstream metadata).

### 3.2 Converter (output side)

The converter turns the list of `ProxyNode`s into the target format. The
**Mihomo converter** generates:

- A `proxies:` block — one entry per node, using field names that match the
  official Mihomo documentation (`servername`, `client-fingerprint`,
  `reality-opts`, `ws-opts`, etc.).
- A `proxy-groups:` block with:
  - **`AUTO`** (`url-test`) — automatically picks the fastest node.
  - **`SELECT`** (`select`) — manual choice; includes `AUTO`, `DIRECT`, and all nodes.
- A `rules:` block with `MATCH,SELECT` (everything goes through the SELECT group).
- A `dns:` block (fake-ip mode, public resolvers).

> Surge and sing-box converters are also wired up (`/surge`, `/sing-box`) and
> share the same parser — they're intentionally minimal placeholders for now.

### 3.3 Dynamic updates ("always fresh")

This is the key production behavior:

- The **cache stores the parsed nodes**, not the rendered YAML.
- The YAML is **regenerated on every request** — so it always reflects the
  current upstream subscription and the current settings.
- The upstream is **re-downloaded automatically** every `CACHE_TTL_SECONDS`
  (default 300s = 5 minutes). When Just My Socks rotates servers, your config
  updates automatically within 5 minutes.
- `?force_refresh=true` forces an immediate re-download (e.g. after a known rotation).
- The `X-Subscription-Fetched-At` response header tells you when the upstream
  was last fetched.
- **No proxy server IP is ever hardcoded** — every node comes from the upstream.

---

## Part 4 — Endpoints

| Method | Path        | Description                              | Content-Type       |
|--------|-------------|------------------------------------------|--------------------|
| GET    | `/`         | Health string `Subscription Converter Running` | `text/plain` |
| GET    | `/health`   | JSON health + cache size                 | `application/json` |
| GET    | `/clash`    | **Mihomo / Clash Meta YAML** (main use)  | `application/yaml` |
| GET    | `/surge`    | Surge config (same parser)               | `text/plain`       |
| GET    | `/sing-box` | sing-box JSON (same parser)              | `application/json` |
| GET    | `/docs`     | Interactive API docs (Swagger UI)        | `text/html`        |

All conversion endpoints (`/clash`, `/surge`, `/sing-box`) take:

- **`?url=<subscription URL>`** (required, URL-encoded)
- **`&force_refresh=true`** (optional) — bypass the cache and re-download now.

**Example:**

```bash
# Get a Clash YAML config
curl "http://localhost:8000/clash?url=https%3A%2F%2Fjmssub.net%2Fgetsub.php%3Fsid%3D1%26token%3Dabc"

# Force a fresh download (bypass 5-min cache)
curl "http://localhost:8000/clash?url=https%3A%2F%2F...&force_refresh=true"

# Check service health
curl http://localhost:8000/health
# {"status":"ok","cache_size":0}
```

---

## Part 5 — Configuration

All settings are **environment variables**. You can set them before running
`uvicorn`, or in `docker-compose.yml` if using Docker.

| Variable                  | Default                              | Explanation                                                            |
|---------------------------|--------------------------------------|------------------------------------------------------------------------|
| `HOST`                    | `0.0.0.0`                            | Network interface to bind. `0.0.0.0` = all interfaces.                 |
| `PORT`                    | `8000`                               | TCP port to listen on.                                                 |
| `WORKERS`                 | `2`                                  | Number of Uvicorn worker processes (more = more concurrent requests).   |
| `CACHE_TTL_SECONDS`       | `300`                                | How often (seconds) the upstream subscription is re-downloaded. 300 = 5 min. |
| `CACHE_MAX_ENTRIES`       | `512`                                | Max distinct subscription URLs kept in the cache.                       |
| `FETCH_TIMEOUT_SECONDS`   | `15`                                 | Timeout (seconds) for downloading the upstream subscription.            |
| `FETCH_USER_AGENT`        | `clash.meta/1.18`                    | User-Agent sent to the upstream provider (some providers need this).    |
| `TEST_URL`                | `https://www.gstatic.com/generate_204` | URL used by the `AUTO` group to test node latency.                   |
| `TEST_INTERVAL`           | `300`                                | How often (seconds) the `AUTO` group re-tests node latency.             |
| `DNS_NAMESERVER`          | Ali/DoH Pub                          | Primary DNS resolvers (comma-separated). **These are public resolvers, not proxy servers.** |
| `DNS_FALLBACK`            | Cloudflare/Google DoH                | Fallback DNS resolvers (comma-separated).                              |
| `DNS_BOOTSTRAP`           | `223.5.5.5,119.29.29.29`             | Plain-DNS bootstrap resolvers.                                         |
| `DNS_FAKE_IP_RANGE`       | `198.18.0.1/16`                      | fake-ip CIDR range for the generated DNS block.                        |
| `DNS_IPV6`                | `false`                              | Enable IPv6 DNS in the generated config.                               |
| `LOG_LEVEL`               | `INFO`                               | Logging verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`).                  |
| `ALLOWED_HOSTS`           | *(empty = all allowed)*              | Comma-separated allow-list of upstream hostnames (SSRF defence).        |

**Example — set a config via environment variables (no Docker):**

```bash
export PORT=9000
export CACHE_TTL_SECONDS=120
uvicorn subscription_converter.app:app --host 0.0.0.0 --port 9000
```

---

## Part 6 — Security

This service is designed to handle sensitive data (subscription URLs contain
credentials). Key safeguards:

- **Subscription URLs and passwords are NEVER logged.** A process-wide logging
  filter redacts any `url=...` value before it reaches any log handler.
- **The cache stores HMAC digests of URLs**, never raw URLs. The HMAC key is
  random per-process, so even a memory dump can't recover the URLs.
- **The Docker container runs as a non-root user** (uid 1001).
- **`ALLOWED_HOSTS`** restricts which upstream providers may be contacted
  (defence-in-depth against SSRF via the `?url=` parameter).

> ⚠️ **If you expose this service publicly**, anyone who knows your subscription
> URL can use your instance. Put it behind an authenticating reverse proxy,
> Cloudflare Access, or a shared-secret path.

---

## Part 7 — Deployment

### 7.1 VPS (with Docker)

```bash
git clone https://github.com/JunWeiLi233/JustMySockets-to-ClashMi.git
cd JustMySockets-to-ClashMi
docker compose up -d --build
```

Put it behind a reverse proxy with HTTPS. Example **Caddyfile** (automatic HTTPS):

```caddyfile
converter.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

### 7.2 Railway / Render / Fly.io

Deploy from this repo; the platform auto-detects the `Dockerfile`. The CMD
honors the `$PORT` environment variable that these platforms inject. Subscribe
with `https://<your-app>.<platform>/clash?url=...`.

### 7.3 Cloudflare Tunnel

Run the converter on a machine that's **not** publicly reachable, then expose
it through Cloudflare Tunnel for free TLS + DDoS protection:

```bash
cloudflared tunnel create converter
cloudflared tunnel route dns converter converter.yourdomain.com
cloudflared tunnel run --url http://localhost:8000 converter
```

Optionally add **Cloudflare Access** in front for authentication.

---

## Part 8 — Development

```bash
# Install runtime + dev dependencies
pip install -r requirements-dev.txt

# Install git hooks
pre-commit install

# Run all quality gates
ruff check subscription-converter
ruff format --check subscription-converter
mypy subscription-converter/subscription_converter
pytest
```

Python 3.12 is the runtime target; CI also tests 3.13 for forward-compatibility.

### Project layout

```
subscription-converter/
├── subscription_converter/         # the importable Python package
│   ├── models.py                   # Pydantic domain models (ProxyNode, etc.)
│   ├── parser_port.py              # parser Protocol interface + registry
│   ├── parsers/                    # per-protocol URI parsers (ss, vmess, ...)
│   ├── subscription_parser.py      # fetch + decode + parse orchestrator
│   ├── converters/                 # output renderers (mihomo, surge, sing-box)
│   ├── converter_registry.py       # output format registry
│   ├── cache.py                    # HMAC-keyed TTL cache
│   ├── config.py                   # immutable Settings (env-driven)
│   └── app.py                      # FastAPI app + endpoints
└── tests/                          # pytest suite (90 tests)
```

---

## License

MIT.

---

# 中文

一个**生产级**服务：接收 Just My Socks(或任意通用)代理订阅 —— 可以是 Base64
数据块、单条 `ss://` 链接,或 `ss://`、`vmess://`、`vless://`、`trojan://`、
`hysteria2://`、`tuic://` 混合列表 —— 将其转换为**完全兼容的 Mihomo / Clash
Meta YAML 配置**,并通过 HTTP 接口对外提供,让 Clash Mi(以及 Clash Verge、
OpenClash 等)直接订阅。

> **为什么需要这个工具?** Just My Socks 提供的订阅格式 Clash Mi 无法识别。本
> 服务会下载该订阅、解码每个节点,并即时重新生成一份干净的 Clash YAML。你的
> Clash 客户端只需要订阅本转换器,完全不需要直接对接上游。

---

## 第 1 部分 —— 快速开始

最快的方式:用 Docker 运行。

```bash
# 1. 克隆
git clone https://github.com/JunWeiLi233/JustMySockets-to-ClashMi.git
cd JustMySockets-to-ClashMi

# 2. 一条命令构建并运行
docker compose up -d --build
```

服务现在监听 `http://localhost:8000`。

在 Clash 客户端中使用以下地址订阅:

```
http://<你的主机>:8000/clash?url=<URL 编码后的订阅地址>
```

> **小贴士 —— 什么是"URL 编码后的订阅地址"?**
> 订阅地址里含有 `?`、`&`、`=` 等字符,会破坏 HTTP 查询字符串。你必须先把整
> 个订阅地址做 URL 编码,再粘贴到 `?url=` 后面。例如:
> ```
> # 原始
> https://jmssub.net/getsub.php?sid=1&token=abc
> # URL 编码后(粘贴到 ?url= 后面)
> https%3A%2F%2Fjmssub.net%2Fgetsub.php%3Fsid%3D1%26token%3Dabc
> ```
> 编码方法:`python -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "<地址>"`
> 或任意在线"URL 编码"工具。

完成 —— 你的 Clash 客户端每次刷新都会拉取一份有效配置。

---

## 第 2 部分 —— 安装(不用 Docker)

如果你想直接用 Python 运行,请按顺序执行以下步骤。

### 2.1 环境要求

- **Python 3.12** 或更高版本(3.13 也可以)。检查版本:
  ```bash
  python3 --version   # 必须 >= 3.12
  ```
- **pip**(随 Python 自带)。
- *(可选)* **Git** 用于克隆代码。

### 2.2 分步操作

```bash
# 1. 获取代码
git clone https://github.com/JunWeiLi233/JustMySockets-to-ClashMi.git
cd JustMySockets-to-ClashMi

# 2. 创建并激活虚拟环境(避免污染系统 Python)
python3.12 -m venv .venv
source .venv/bin/activate          # Windows 用: .venv\Scripts\activate

# 3. 安装所有必需的 Python 包
pip install -r requirements.txt
```

> **`requirements.txt` 里有什么?** 它固定了运行时依赖:`fastapi`(Web 框架)、
> `uvicorn`(ASGI 服务器)、`httpx`(用于下载上游订阅的 HTTP 客户端)、
> `pydantic`(代理节点的数据校验)、`PyYAML`(生成 Clash YAML)。执行完这一步,
> 你就拥有运行本服务所需的全部依赖。

```bash
# 4. 运行
uvicorn subscription_converter.app:app --host 0.0.0.0 --port 8000
```

你会看到 `Uvicorn running on http://0.0.0.0:8000`。用浏览器打开
`http://localhost:8000/`,应显示 `Subscription Converter Running`。

### 2.3 (可选)开发依赖

如果你要开发或跑测试,还要安装开发工具:

```bash
pip install -r requirements-dev.txt
```

这会额外安装 `pytest` + `pytest-asyncio`(测试)、`respx`(HTTP 模拟)、
`ruff`(代码检查/格式化)、`mypy`(类型检查)、`pre-commit`(Git 钩子)。

---

## 第 3 部分 —— 工作原理

理解这条流水线有助于排查问题和扩展功能。

```
┌──────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│  Clash 客户端     │────▶│  /clash      │────▶│   解析器     │────▶│  转换器     │
│  (Clash Mi ...)  │◀────│  接口         │◀────│ (解码+解析)  │◀────│ (Mihomo    │
│                  │     │  (FastAPI)   │     │             │     │  YAML)     │
└──────────────────┘     └──────────────┘     └─────────────┘     └────────────┘
                                │                     ▲
                                │                     │
                          ┌─────▼─────┐         ┌─────┴─────┐
                          │   缓存     │         │ 上游订阅   │
                          │ (5 分钟)   │◀────────│  地址      │
                          └───────────┘         └───────────┘
```

### 3.1 解析器(输入侧)

解析器**与供应商无关** —— 它不关心是谁发布的订阅。它会:

1. **下载**订阅内容(通过 `httpx`)。
2. **识别格式**:纯链接列表、单条链接,或 Base64 数据块。Base64 会自动解码
   (兼容缺失填充和 urlsafe 变体)。
3. **把每条链接解析**成标准化的 `ProxyNode`。支持的协议:
   - `ss://` —— Shadowsocks(SIP002 + 旧版;`obfs-local` → `obfs`)
   - `ssr://` —— ShadowsocksR
   - `vmess://` —— VMess(v2rayN JSON;ws/grpc/h2 传输)
   - `vless://` —— VLESS(含 REALITY:公钥/短ID/指纹/flow)
   - `trojan://` —— Trojan(ws/grpc)
   - `hysteria2://` / `hy2://` —— Hysteria2(salamander 混淆 + 带宽)
   - `hysteria://` —— Hysteria v1
   - `tuic://` —— TUIC v5
4. **返回**一个 `Subscription`(节点列表 + 安全的上游元数据)。

### 3.2 转换器(输出侧)

转换器把 `ProxyNode` 列表转换成目标格式。**Mihomo 转换器**会生成:

- `proxies:` 块 —— 每个节点一条,字段名严格遵循 Mihomo 官方文档
  (`servername`、`client-fingerprint`、`reality-opts`、`ws-opts` 等)。
- `proxy-groups:` 块,包含:
  - **`AUTO`**(`url-test`)—— 自动选择最快的节点。
  - **`SELECT`**(`select`)—— 手动选择;包含 `AUTO`、`DIRECT` 和所有节点。
- `rules:` 块,含 `MATCH,SELECT`(所有流量走 SELECT 组)。
- `dns:` 块(fake-ip 模式,公共解析器)。

> Surge 和 sing-box 转换器也已接好(`/surge`、`/sing-box`),共用同一个解析
> 器 —— 目前是刻意精简的占位实现。

### 3.3 动态更新("始终最新")

这是关键的生产级行为:

- **缓存里存的是解析后的节点**,不是渲染好的 YAML。
- YAML **每次请求都重新生成** —— 因此始终反映当前的上游订阅和当前设置。
- 上游**每 `CACHE_TTL_SECONDS`(默认 300 秒 = 5 分钟)自动重新下载**。当
  Just My Socks 轮换服务器时,你的配置会在 5 分钟内自动更新。
- `?force_refresh=true` 可强制立即重新下载(例如已知刚轮换过)。
- 响应头 `X-Subscription-Fetched-At` 告诉你上游上次下载的时间。
- **绝不硬编码任何代理服务器 IP** —— 每个节点都来自上游。

---

## 第 4 部分 —— 接口

| 方法 | 路径        | 说明                                    | Content-Type       |
|------|-------------|-----------------------------------------|--------------------|
| GET  | `/`         | 健康检查字符串 `Subscription Converter Running` | `text/plain` |
| GET  | `/health`   | JSON 健康状态 + 缓存大小                | `application/json` |
| GET  | `/clash`    | **Mihomo / Clash Meta YAML**(主要用途) | `application/yaml` |
| GET  | `/surge`    | Surge 配置(同一解析器)                | `text/plain`       |
| GET  | `/sing-box` | sing-box JSON(同一解析器)             | `application/json` |
| GET  | `/docs`     | 交互式 API 文档(Swagger UI)           | `text/html`        |

所有转换接口(`/clash`、`/surge`、`/sing-box`)都接受:

- **`?url=<订阅地址>`**(必填,需 URL 编码)
- **`&force_refresh=true`**(可选)—— 绕过缓存,立即重新下载。

**示例:**

```bash
# 获取 Clash YAML 配置
curl "http://localhost:8000/clash?url=https%3A%2F%2Fjmssub.net%2Fgetsub.php%3Fsid%3D1%26token%3Dabc"

# 强制刷新(绕过 5 分钟缓存)
curl "http://localhost:8000/clash?url=https%3A%2F%2F...&force_refresh=true"

# 检查服务健康
curl http://localhost:8000/health
# {"status":"ok","cache_size":0}
```

---

## 第 5 部分 —— 配置

所有设置都是**环境变量**。你可以在运行 `uvicorn` 前设置,或在使用 Docker 时
写在 `docker-compose.yml` 里。

| 变量                      | 默认值                               | 说明                                                    |
|---------------------------|--------------------------------------|---------------------------------------------------------|
| `HOST`                    | `0.0.0.0`                            | 绑定的网卡。`0.0.0.0` = 所有网卡。                       |
| `PORT`                    | `8000`                               | 监听的 TCP 端口。                                        |
| `WORKERS`                 | `2`                                  | Uvicorn worker 进程数(越多并发越高)。                   |
| `CACHE_TTL_SECONDS`       | `300`                                | 上游订阅多久(秒)重新下载一次。300 = 5 分钟。            |
| `CACHE_MAX_ENTRIES`       | `512`                                | 缓存中最多保留多少个不同的订阅地址。                     |
| `FETCH_TIMEOUT_SECONDS`   | `15`                                 | 下载上游订阅的超时时间(秒)。                            |
| `FETCH_USER_AGENT`        | `clash.meta/1.18`                    | 发送给上游的 User-Agent(部分供应商需要特定 UA)。        |
| `TEST_URL`                | `https://www.gstatic.com/generate_204` | `AUTO` 组测速用的地址。                              |
| `TEST_INTERVAL`           | `300`                                | `AUTO` 组多久(秒)重新测速一次。                        |
| `DNS_NAMESERVER`          | Ali/DoH Pub                          | 主 DNS 解析器(逗号分隔)。**这些是公共解析器,不是代理服务器。** |
| `DNS_FALLBACK`            | Cloudflare/Google DoH                | 备用 DNS 解析器(逗号分隔)。                             |
| `DNS_BOOTSTRAP`           | `223.5.5.5,119.29.29.29`             | 明文 DNS 引导解析器。                                    |
| `DNS_FAKE_IP_RANGE`       | `198.18.0.1/16`                      | 生成 DNS 块的 fake-ip CIDR 范围。                        |
| `DNS_IPV6`                | `false`                              | 是否在生成配置中启用 IPv6 DNS。                          |
| `LOG_LEVEL`               | `INFO`                               | 日志级别(`DEBUG`/`INFO`/`WARNING`/`ERROR`)。            |
| `ALLOWED_HOSTS`           | *(空 = 全部允许)*                    | 允许的上游主机名白名单(逗号分隔,防 SSRF)。             |

**示例 —— 用环境变量配置(无 Docker):**

```bash
export PORT=9000
export CACHE_TTL_SECONDS=120
uvicorn subscription_converter.app:app --host 0.0.0.0 --port 9000
```

---

## 第 6 部分 —— 安全

本服务会处理敏感数据(订阅地址里含凭据)。关键防护措施:

- **订阅地址和密码绝不写入日志。** 进程级的日志过滤器会在任何日志处理器收到
  记录前,抹除所有 `url=...` 的值。
- **缓存只存 URL 的 HMAC 摘要**,不存原始 URL。HMAC 密钥每个进程随机生成,
  即使内存转储也无法还原地址。
- **Docker 容器以非 root 用户运行**(uid 1001)。
- **`ALLOWED_HOSTS`** 限制可访问哪些上游供应商(防 SSRF 的纵深防御)。

> ⚠️ **如果你把本服务公开到互联网**,任何知道你订阅地址的人都能使用你的实
> 例。请放在带鉴权的反向代理、Cloudflare Access 或共享密钥路径后面。

---

## 第 7 部分 —— 部署

### 7.1 VPS(用 Docker)

```bash
git clone https://github.com/JunWeiLi233/JustMySockets-to-ClashMi.git
cd JustMySockets-to-ClashMi
docker compose up -d --build
```

建议放在带 HTTPS 的反向代理后面。**Caddyfile** 示例(自动 HTTPS):

```caddyfile
converter.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

### 7.2 Railway / Render / Fly.io

从此仓库部署,平台会自动识别 `Dockerfile`。CMD 会读取这些平台注入的 `$PORT`
环境变量。用 `https://<你的应用>.<平台>/clash?url=...` 订阅。

### 7.3 Cloudflare Tunnel

把转换器跑在**不**直接对公网开放的机器上,再通过 Cloudflare Tunnel 暴露,获得
免费的 TLS + DDoS 防护:

```bash
cloudflared tunnel create converter
cloudflared tunnel route dns converter converter.yourdomain.com
cloudflared tunnel run --url http://localhost:8000 converter
```

可选地,在前方加 **Cloudflare Access** 实现身份认证。

---

## 第 8 部分 —— 开发

```bash
# 安装运行时 + 开发依赖
pip install -r requirements-dev.txt

# 安装 Git 钩子
pre-commit install

# 运行所有质量检查
ruff check subscription-converter
ruff format --check subscription-converter
mypy subscription-converter/subscription_converter
pytest
```

运行时目标为 Python 3.12;CI 也会测试 3.13 以保证前向兼容。

### 项目结构

```
subscription-converter/
├── subscription_converter/         # 可导入的 Python 包
│   ├── models.py                   # Pydantic 领域模型(ProxyNode 等)
│   ├── parser_port.py              # 解析器 Protocol 接口 + 注册表
│   ├── parsers/                    # 各协议 URI 解析器(ss、vmess ...)
│   ├── subscription_parser.py      # 下载 + 解码 + 解析 编排器
│   ├── converters/                 # 输出渲染器(mihomo、surge、sing-box)
│   ├── converter_registry.py       # 输出格式注册表
│   ├── cache.py                    # HMAC 键控的 TTL 缓存
│   ├── config.py                   # 不可变 Settings(环境变量驱动)
│   └── app.py                      # FastAPI 应用 + 接口
└── tests/                          # pytest 测试套件(90 个测试)
```

---

## 许可证

MIT。
