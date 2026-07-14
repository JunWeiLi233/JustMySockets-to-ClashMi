"""Self-contained, privacy-preserving frontend for the converter.

The page intentionally has no external assets, analytics, network-submitting
HTML forms, or browser storage. A subscription URL remains in the local DOM
until the user explicitly asks the same-origin ``/api/check`` endpoint to
validate it.
"""

from __future__ import annotations

import html

__all__ = ["render_frontend"]


def render_frontend(*, nonce: str) -> str:
    """Return the converter UI with a request-scoped CSP nonce."""
    safe_nonce = html.escape(nonce, quote=True)
    return _PAGE.replace("__CSP_NONCE__", safe_nonce)


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <meta name="color-scheme" content="dark">
  <title>JMS Config Bridge</title>
  <style nonce="__CSP_NONCE__">
    :root {
      color-scheme: dark;
      --ink: #f7f4e9;
      --muted: #9ca8b6;
      --faint: #657181;
      --base: #07100f;
      --panel: rgba(14, 27, 25, 0.86);
      --panel-strong: #112422;
      --line: rgba(177, 203, 195, 0.16);
      --mint: #75f0c5;
      --mint-strong: #2cd6a0;
      --amber: #f4bd68;
      --danger: #ff8d8d;
      --shadow: 0 28px 70px rgba(0, 0, 0, 0.34);
    }

    * { box-sizing: border-box; }

    html { min-height: 100%; background: var(--base); }

    body {
      min-height: 100vh;
      margin: 0;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 14% 5%, rgba(44, 214, 160, 0.18), transparent 31rem),
        radial-gradient(circle at 92% 12%, rgba(244, 189, 104, 0.12), transparent 26rem),
        linear-gradient(145deg, #07100f 0%, #091514 52%, #07100f 100%);
    }

    body::before {
      position: fixed;
      inset: 0;
      pointer-events: none;
      content: "";
      opacity: 0.17;
      background-image:
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: linear-gradient(to bottom, black, transparent 88%);
    }

    button, input, select, textarea { font: inherit; }
    button, select { cursor: pointer; }

    .shell {
      position: relative;
      width: min(1160px, calc(100% - 40px));
      margin: 0 auto;
      padding: 28px 0 54px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 3px 0 54px;
    }

    .brand { display: flex; align-items: center; gap: 12px; }

    .brand-mark {
      display: grid;
      width: 38px;
      height: 38px;
      place-items: center;
      border: 1px solid rgba(117, 240, 197, 0.42);
      border-radius: 12px;
      color: var(--mint);
      background: rgba(117, 240, 197, 0.08);
      box-shadow: inset 0 0 22px rgba(117, 240, 197, 0.07);
    }

    .brand-mark svg { width: 21px; height: 21px; }
    .brand-copy strong { display: block; letter-spacing: -0.02em; }
    .brand-copy span { display: block; margin-top: 2px; color: var(--faint); font-size: 12px; }

    .live {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #b7c4c0;
      font-size: 13px;
    }

    .live-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--mint);
      box-shadow: 0 0 14px rgba(117, 240, 197, 0.75);
    }

    .hero { max-width: 830px; margin-bottom: 36px; }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 16px;
      color: var(--mint);
      font-size: 12px;
      font-weight: 750;
      letter-spacing: 0.13em;
      text-transform: uppercase;
    }

    h1 {
      max-width: 780px;
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(44px, 7.2vw, 78px);
      font-weight: 500;
      letter-spacing: -0.055em;
      line-height: 0.98;
    }

    h1 em { color: var(--mint); font-style: italic; }

    .lead {
      max-width: 650px;
      margin: 22px 0 0;
      color: var(--muted);
      font-size: clamp(16px, 2vw, 19px);
      line-height: 1.65;
    }

    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(280px, .8fr);
      gap: 18px;
      align-items: start;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(20px);
    }

    .builder { padding: clamp(22px, 4vw, 36px); }

    .card-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 28px;
    }

    h2 { margin: 0; font-size: 20px; letter-spacing: -0.025em; }
    .card-head p { margin: 6px 0 0; color: var(--faint); font-size: 13px; }

    .step {
      display: grid;
      min-width: 34px;
      height: 34px;
      place-items: center;
      border: 1px solid var(--line);
      border-radius: 50%;
      color: var(--mint);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
    }

    label.field-label {
      display: block;
      margin-bottom: 9px;
      color: #d8dfdc;
      font-size: 13px;
      font-weight: 700;
    }

    .secret-field { position: relative; }

    input[type="password"], input[type="text"], select, textarea {
      width: 100%;
      border: 1px solid rgba(177, 203, 195, 0.2);
      border-radius: 14px;
      outline: none;
      color: var(--ink);
      background: rgba(2, 10, 9, 0.66);
      transition: border-color .18s ease, box-shadow .18s ease, background .18s ease;
    }

    input[type="password"], input[type="text"] {
      min-height: 54px;
      padding: 0 54px 0 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
    }

    input:focus, select:focus, textarea:focus {
      border-color: rgba(117, 240, 197, 0.72);
      box-shadow: 0 0 0 4px rgba(117, 240, 197, 0.09);
      background: rgba(4, 15, 13, 0.86);
    }

    .reveal {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 38px;
      height: 38px;
      border: 0;
      border-radius: 10px;
      color: var(--muted);
      background: transparent;
    }

    .reveal:hover { color: var(--ink); background: rgba(255,255,255,.06); }
    .reveal svg { width: 18px; height: 18px; vertical-align: middle; }

    .hint { margin: 8px 0 0; color: var(--faint); font-size: 12px; line-height: 1.5; }

    .options {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-top: 22px;
    }

    select { min-height: 48px; padding: 0 40px 0 14px; }

    .toggle-wrap {
      display: flex;
      min-height: 48px;
      align-items: center;
      gap: 11px;
      padding: 0 14px;
      border: 1px solid rgba(177, 203, 195, 0.14);
      border-radius: 14px;
      color: var(--muted);
      background: rgba(2, 10, 9, 0.38);
      font-size: 13px;
    }

    input[type="checkbox"] { width: 17px; height: 17px; accent-color: var(--mint-strong); }

    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }

    .button {
      min-height: 46px;
      padding: 0 18px;
      border: 1px solid transparent;
      border-radius: 13px;
      font-weight: 750;
      transition: transform .16s ease, border-color .16s ease, background .16s ease, opacity .16s ease;
    }

    .button:hover:not(:disabled) { transform: translateY(-1px); }
    .button:disabled { cursor: not-allowed; opacity: .43; }
    .button.primary { color: #062019; background: var(--mint); box-shadow: 0 10px 30px rgba(44,214,160,.16); }
    .button.primary:hover:not(:disabled) { background: #93f7d4; }
    .button.secondary { border-color: var(--line); color: var(--ink); background: rgba(255,255,255,.035); }
    .button.ghost { padding: 0 12px; color: var(--faint); background: transparent; }

    .status {
      min-height: 22px;
      margin: 14px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }

    .status[data-kind="success"] { color: var(--mint); }
    .status[data-kind="error"] { color: var(--danger); }
    .status[data-kind="working"] { color: var(--amber); }

    .result {
      margin-top: 26px;
      padding-top: 24px;
      border-top: 1px solid var(--line);
    }

    .result[hidden] { display: none; }
    textarea { min-height: 112px; resize: vertical; padding: 14px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; line-height: 1.55; }

    .aside { overflow: hidden; }
    .aside-top { padding: 26px; border-bottom: 1px solid var(--line); background: linear-gradient(150deg, rgba(117,240,197,.08), transparent 65%); }
    .lock {
      display: grid;
      width: 42px;
      height: 42px;
      margin-bottom: 17px;
      place-items: center;
      border-radius: 13px;
      color: var(--mint);
      background: rgba(117,240,197,.1);
    }
    .lock svg { width: 21px; height: 21px; }
    .aside h2 { font-family: Georgia, "Times New Roman", serif; font-size: 25px; font-weight: 500; }
    .aside-top p { margin: 10px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }

    .privacy-list { display: grid; gap: 0; padding: 8px 26px 18px; }
    .privacy-item { display: grid; grid-template-columns: 22px 1fr; gap: 10px; padding: 15px 0; border-bottom: 1px solid rgba(177,203,195,.09); }
    .privacy-item:last-child { border-bottom: 0; }
    .check { color: var(--mint); font-weight: 800; }
    .privacy-item strong { display: block; margin-bottom: 4px; font-size: 13px; }
    .privacy-item span { display: block; color: var(--faint); font-size: 12px; line-height: 1.5; }

    .howto { margin-top: 18px; padding: 24px 26px; }
    .howto h2 { margin-bottom: 18px; }
    .steps { display: grid; gap: 14px; counter-reset: steps; }
    .how-step { display: grid; grid-template-columns: 28px 1fr; gap: 10px; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .how-step::before { counter-increment: steps; content: counter(steps); display: grid; width: 24px; height: 24px; place-items: center; border: 1px solid var(--line); border-radius: 50%; color: var(--mint); font-size: 11px; }
    .how-step strong { color: var(--ink); }

    footer { display: flex; justify-content: space-between; gap: 20px; margin-top: 24px; padding: 0 4px; color: var(--faint); font-size: 11px; line-height: 1.5; }
    footer a { color: #8ba69d; text-underline-offset: 3px; }

    @media (max-width: 820px) {
      .shell { width: min(100% - 24px, 660px); padding-top: 18px; }
      .topbar { padding-bottom: 38px; }
      .grid { grid-template-columns: 1fr; }
      .aside { order: 2; }
      .options { grid-template-columns: 1fr; }
      h1 { font-size: clamp(42px, 13vw, 64px); }
    }

    @media (max-width: 480px) {
      .brand-copy span { display: none; }
      .live { font-size: 12px; }
      .builder { padding: 22px 18px; }
      .actions .button { flex: 1 1 100%; }
      footer { display: block; }
      footer span { display: block; margin-bottom: 6px; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand" aria-label="JMS Config Bridge">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8.5 15.5 15.5 8.5M7 7h.01M17 17h.01"/><rect x="3" y="3" width="18" height="18" rx="6"/></svg>
        </div>
        <div class="brand-copy"><strong>JMS Config Bridge</strong><span>Private subscription conversion</span></div>
      </div>
      <div class="live"><span class="live-dot" aria-hidden="true"></span>Service online</div>
    </header>

    <section class="hero">
      <p class="eyebrow">Clash Mi ready · macOS friendly</p>
      <h1>Turn one private link into a <em>clean config.</em></h1>
      <p class="lead">Paste your Just My Socks subscription once. The link is encoded here in your browser, ready to add directly to Clash Mi, Clash Verge, or OpenClash.</p>
    </section>

    <div class="grid">
      <section class="card builder" aria-labelledby="builder-title">
        <div class="card-head">
          <div><h2 id="builder-title">Build your subscription URL</h2><p>No quotes, Terminal commands, or manual encoding.</p></div>
          <span class="step" aria-hidden="true">01</span>
        </div>

        <form id="builder" autocomplete="off" novalidate>
          <label class="field-label" for="source-url">Original JMS subscription link</label>
          <div class="secret-field">
            <input id="source-url" name="source-url" type="password" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="4096" placeholder="https://jmssub.net/…" aria-describedby="url-hint" required>
            <button class="reveal" id="reveal" type="button" aria-label="Show subscription link" aria-pressed="false" title="Show or hide link">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6S2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.6"/></svg>
            </button>
          </div>
          <p class="hint" id="url-hint">Kept only in this tab. HTTPS is required to protect it in transit.</p>

          <div class="options">
            <div>
              <label class="field-label" for="format">Client format</label>
              <select id="format" name="format">
                <option value="clash">Clash / Mihomo (recommended)</option>
                <option value="sing-box">sing-box</option>
                <option value="surge">Surge</option>
              </select>
            </div>
            <div>
              <span class="field-label">Refresh behavior</span>
              <label class="toggle-wrap" for="force-refresh">
                <input id="force-refresh" type="checkbox">
                Always bypass 5-minute cache
              </label>
            </div>
          </div>

          <div class="actions">
            <button class="button primary" type="submit">Generate secure link</button>
            <button class="button secondary" id="check-link" type="button" disabled>Check connection</button>
          </div>
          <p class="status" id="status" role="status" aria-live="polite"></p>
        </form>

        <section class="result" id="result" aria-labelledby="result-label" hidden>
          <label class="field-label" id="result-label" for="output">Clash Mi subscription URL</label>
          <textarea id="output" readonly autocomplete="off" spellcheck="false"></textarea>
          <div class="actions">
            <button class="button primary" id="copy" type="button">Copy subscription URL</button>
            <button class="button ghost" id="clear" type="button">Clear sensitive data</button>
          </div>
        </section>
      </section>

      <div>
        <aside class="card aside" aria-labelledby="privacy-title">
          <div class="aside-top">
            <div class="lock" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4.5" y="10" width="15" height="10" rx="3"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10M12 14v2.5"/></svg></div>
            <h2 id="privacy-title">Private by design</h2>
            <p>The page is intentionally self-contained and sends nothing until you choose “Check connection.”</p>
          </div>
          <div class="privacy-list">
            <div class="privacy-item"><span class="check">✓</span><div><strong>No analytics or third-party assets</strong><span>No trackers, fonts, CDNs, or external JavaScript.</span></div></div>
            <div class="privacy-item"><span class="check">✓</span><div><strong>No browser storage</strong><span>Your link is never written to cookies, localStorage, or sessionStorage.</span></div></div>
            <div class="privacy-item"><span class="check">✓</span><div><strong>No shared config caching</strong><span>Generated proxy credentials are marked private and non-cacheable.</span></div></div>
            <div class="privacy-item"><span class="check">✓</span><div><strong>Memory-only server cache</strong><span>Opaque HMAC keys; parsed nodes expire automatically and are never persisted.</span></div></div>
          </div>
        </aside>

        <section class="card howto" aria-labelledby="how-title">
          <h2 id="how-title">Add to Clash Mi</h2>
          <div class="steps">
            <div class="how-step"><span><strong>Paste</strong> the original JMS link above.</span></div>
            <div class="how-step"><span><strong>Generate and copy</strong> the new subscription URL.</span></div>
            <div class="how-step"><span>In Clash Mi, open <strong>Profiles / Subscriptions</strong>, add from URL, then update.</span></div>
          </div>
        </section>
      </div>
    </div>

    <footer><span>Do not share the generated URL—it is a bearer credential.</span><a href="/health" rel="noreferrer">Service health</a></footer>
  </main>

  <script nonce="__CSP_NONCE__">
    (() => {
      "use strict";
      const form = document.getElementById("builder");
      const source = document.getElementById("source-url");
      const format = document.getElementById("format");
      const forceRefresh = document.getElementById("force-refresh");
      const reveal = document.getElementById("reveal");
      const result = document.getElementById("result");
      const output = document.getElementById("output");
      const status = document.getElementById("status");
      const checkButton = document.getElementById("check-link");
      const copyButton = document.getElementById("copy");
      const clearButton = document.getElementById("clear");
      const paths = {clash: "/clash", "sing-box": "/sing-box", surge: "/surge"};

      const setStatus = (message, kind = "") => {
        status.textContent = message;
        status.dataset.kind = kind;
      };

      const validate = () => {
        const raw = source.value.trim();
        if (!raw) throw new Error("Paste your original JMS subscription link first.");
        if (raw.length > 4096) throw new Error("The subscription link is too long.");
        let parsed;
        try { parsed = new URL(raw); } catch (_) { throw new Error("That is not a complete URL."); }
        if (parsed.protocol !== "https:") throw new Error("Use an HTTPS subscription link to keep it confidential in transit.");
        if (!parsed.hostname) throw new Error("The subscription link has no hostname.");
        return raw;
      };

      const build = () => {
        const raw = validate();
        const endpoint = paths[format.value] || paths.clash;
        const generated = `${window.location.origin}${endpoint}?url=${encodeURIComponent(raw)}${forceRefresh.checked ? "&force_refresh=true" : ""}`;
        output.value = generated;
        result.hidden = false;
        checkButton.disabled = false;
        setStatus("Link generated locally. It has not been sent anywhere.", "success");
        return raw;
      };

      const invalidateResult = () => {
        output.value = "";
        result.hidden = true;
        checkButton.disabled = true;
        setStatus("");
      };

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        try { build(); } catch (error) { invalidateResult(); setStatus(error.message, "error"); }
      });

      source.addEventListener("input", invalidateResult);
      format.addEventListener("change", invalidateResult);
      forceRefresh.addEventListener("change", invalidateResult);

      reveal.addEventListener("click", () => {
        const showing = source.type === "text";
        source.type = showing ? "password" : "text";
        reveal.setAttribute("aria-pressed", String(!showing));
        reveal.setAttribute("aria-label", showing ? "Show subscription link" : "Hide subscription link");
      });

      copyButton.addEventListener("click", async () => {
        if (!output.value) return;
        try {
          await navigator.clipboard.writeText(output.value);
        } catch (_) {
          output.focus();
          output.select();
          document.execCommand("copy");
        }
        setStatus("Copied. Paste it into Clash Mi → Profiles / Subscriptions.", "success");
      });

      checkButton.addEventListener("click", async () => {
        let raw;
        try { raw = build(); } catch (error) { setStatus(error.message, "error"); return; }
        checkButton.disabled = true;
        setStatus("Checking the upstream privately…", "working");
        try {
          const response = await fetch("/api/check", {
            method: "POST",
            credentials: "same-origin",
            cache: "no-store",
            referrerPolicy: "no-referrer",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: raw, format: format.value, force_refresh: forceRefresh.checked})
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.message || "The converter rejected this link.");
          setStatus(`Connection works — ${payload.nodes} proxy node${payload.nodes === 1 ? "" : "s"} found.`, "success");
        } catch (error) {
          setStatus(error.message || "Connection check failed.", "error");
        } finally {
          checkButton.disabled = !output.value;
          raw = "";
        }
      });

      const clearSensitiveData = () => {
        source.value = "";
        source.type = "password";
        output.value = "";
        result.hidden = true;
        checkButton.disabled = true;
        forceRefresh.checked = false;
        reveal.setAttribute("aria-pressed", "false");
        setStatus("Sensitive data cleared from this tab.", "success");
        source.focus();
      };

      clearButton.addEventListener("click", clearSensitiveData);
      window.addEventListener("pagehide", () => {
        source.value = "";
        output.value = "";
      });
    })();
  </script>
</body>
</html>
"""
