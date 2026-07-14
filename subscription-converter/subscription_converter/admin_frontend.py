"""Self-contained, secret-minimising admin pages."""

from __future__ import annotations

from html import escape

__all__ = ["render_admin_dashboard", "render_admin_enrollment"]


def _head(nonce: str, title: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow, noarchive">
  <title>{escape(title)}</title>
  <style nonce="{escape(nonce)}">
    :root {{ color-scheme: dark; font: 16px/1.5 system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0b1020; color: #eef2ff; }}
    main {{ width: min(1100px, calc(100% - 32px)); margin: 48px auto; }}
    h1 {{ font-size: clamp(1.8rem, 5vw, 3rem); margin-bottom: .3rem; }}
    .muted {{ color: #a9b4d0; }}
    .panel, .metric {{ background: #151d33; border: 1px solid #2a385c; border-radius: 14px; }}
    .panel {{ padding: 22px; margin-top: 24px; overflow-x: auto; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 24px; }}
    .metric {{ padding: 16px; }}
    .metric strong {{ display: block; font-size: 1.8rem; }}
    label {{ display: block; margin: 16px 0 8px; font-weight: 650; }}
    input {{ width: 100%; padding: 12px; border-radius: 9px; border: 1px solid #53658e; background: #090e1b; color: inherit; }}
    button {{ border: 0; border-radius: 9px; padding: 10px 14px; color: white; background: #5965ee; cursor: pointer; font-weight: 700; }}
    button.danger {{ background: #a72b3c; }}
    button:disabled {{ opacity: .55; cursor: wait; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #2a385c; }}
    th {{ color: #a9b4d0; font-size: .85rem; }}
    code {{ color: #c6d1f5; }}
    #message {{ min-height: 1.5em; margin-top: 14px; }}
    a {{ color: #aeb8ff; }}
  </style>
</head>"""


def render_admin_enrollment(*, nonce: str) -> str:
    """Render the one-time admin browser enrollment form."""
    return (
        _head(nonce, "Enroll admin device")
        + f"""
<body><main>
  <h1>Enroll this browser</h1>
  <p class="muted">This page works only once. The resulting admin credential is bound to this browser profile and stored in Secure, HttpOnly cookies.</p>
  <section class="panel">
    <form id="enroll-form">
      <label for="secret">Admin bootstrap secret</label>
      <input id="secret" name="secret" type="password" autocomplete="off" required minlength="43" maxlength="128">
      <p><button type="submit">Enroll this browser</button></p>
      <p id="message" role="status" aria-live="polite"></p>
    </form>
  </section>
</main>
<script nonce="{escape(nonce)}">
  const form = document.getElementById("enroll-form");
  const secret = document.getElementById("secret");
  const message = document.getElementById("message");
  form.addEventListener("submit", async (event) => {{
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    message.textContent = "Enrolling…";
    try {{
      const response = await fetch("/api/admin/enroll", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{bootstrap_secret: secret.value}}),
        credentials: "same-origin"
      }});
      secret.value = "";
      if (!response.ok) {{
        message.textContent = response.status === 429 ? "Too many attempts. Try later." : "Enrollment unavailable.";
        return;
      }}
      location.replace("/admin");
    }} catch (_) {{
      message.textContent = "The server could not be reached.";
    }} finally {{ button.disabled = false; }}
  }});
</script>
</body></html>"""
    )


def render_admin_dashboard(*, nonce: str, csrf_token: str) -> str:
    """Render an admin dashboard that receives metadata only."""
    return (
        _head(nonce, "Subscription admin")
        + f"""
<body><main>
  <h1>Subscription admin</h1>
  <p class="muted">Pseudonymous operational metadata only. Upstream URLs, proxy credentials, access tokens, and management keys are never sent to this page.</p>
  <section class="metrics" aria-label="Overview">
    <div class="metric"><span class="muted">Active links</span><strong id="active">—</strong></div>
    <div class="metric"><span class="muted">Capacity</span><strong id="capacity">—</strong></div>
    <div class="metric"><span class="muted">User devices</span><strong id="users">—</strong></div>
    <div class="metric"><span class="muted">Networks</span><strong id="networks">—</strong></div>
  </section>
  <section class="panel">
    <table>
      <thead><tr><th>Link ref</th><th>User ref</th><th>Network ref</th><th>Format</th><th>Created</th><th>Action</th></tr></thead>
      <tbody id="links"></tbody>
    </table>
    <p id="message" class="muted" role="status" aria-live="polite"></p>
  </section>
  <p><a href="/">Public converter</a></p>
</main>
<script nonce="{escape(nonce)}">
  const csrf = "{escape(csrf_token)}";
  const tbody = document.getElementById("links");
  const message = document.getElementById("message");
  function cell(row, text) {{ const td = document.createElement("td"); td.textContent = text; row.append(td); }}
  async function closeLink(linkRef, button) {{
    if (!confirm("Permanently close this subscription link?")) return;
    button.disabled = true;
    const response = await fetch("/api/admin/links/close", {{
      method: "POST",
      credentials: "same-origin",
      headers: {{"Content-Type": "application/json", "X-Admin-CSRF": csrf}},
      body: JSON.stringify({{link_ref: linkRef}})
    }});
    if (response.ok) await load(); else {{ message.textContent = "Close failed."; button.disabled = false; }}
  }}
  async function load() {{
    const response = await fetch("/api/admin/overview", {{credentials: "same-origin"}});
    if (!response.ok) {{ location.replace("/"); return; }}
    const data = await response.json();
    document.getElementById("active").textContent = String(data.active);
    document.getElementById("capacity").textContent = String(data.limit);
    document.getElementById("users").textContent = String(data.unique_users);
    document.getElementById("networks").textContent = String(data.unique_networks);
    tbody.replaceChildren();
    for (const link of data.links) {{
      const row = document.createElement("tr");
      cell(row, link.link_ref.slice(0, 10)); cell(row, link.user_ref); cell(row, link.network_ref);
      cell(row, link.format); cell(row, new Date(link.created_at * 1000).toLocaleString());
      const action = document.createElement("td"); const button = document.createElement("button");
      button.type = "button"; button.className = "danger"; button.textContent = "Close";
      button.addEventListener("click", () => closeLink(link.link_ref, button)); action.append(button); row.append(action); tbody.append(row);
    }}
    message.textContent = data.unidentified_links ? `${{data.unidentified_links}} legacy link(s) have no user identity.` : "";
  }}
  load();
</script>
</body></html>"""
    )
