"""Self-contained, privacy-preserving frontend for the converter.

The page intentionally has no external assets or analytics. A random HttpOnly
device cookie supports fair-use quotas. Sensitive values are sent only to
same-origin JSON endpoints when the user explicitly tests, creates, or closes
a durable subscription link.
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

    .capacity {
      padding: 7px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: rgba(255,255,255,.025);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .02em;
    }

    .capacity[data-state="open"] { color: var(--mint); border-color: rgba(117,240,197,.28); }
    .capacity[data-state="closed"] { color: var(--amber); border-color: rgba(244,189,104,.3); }

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

    .info-tile {
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

    .info-tile::before { content: "∞"; color: var(--mint); font-size: 19px; }

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
    .button.danger { border-color: rgba(255,141,141,.28); color: #ffd0d0; background: rgba(255,141,141,.07); }
    .button.danger:hover:not(:disabled) { background: rgba(255,141,141,.12); }

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
    .result .field-label:not(:first-child) { margin-top: 22px; }
    .recovery-note { margin: 9px 0 0; color: var(--amber); font-size: 12px; line-height: 1.55; }
    .result-meta { margin: 10px 0 0; color: var(--faint); font-size: 12px; line-height: 1.55; }

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

    .manage { margin-top: 18px; padding: 24px 26px; }
    .manage h2 { margin-bottom: 8px; }
    .manage > p { margin: 0 0 18px; color: var(--muted); font-size: 12px; line-height: 1.6; }

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
        <div class="brand-copy"><strong>JMS Config Bridge</strong><span>Durable private subscriptions</span></div>
      </div>
      <div class="live"><span class="live-dot" aria-hidden="true"></span><span class="capacity" id="capacity" data-state="checking">Checking capacity…</span></div>
    </header>

    <section class="hero">
      <p class="eyebrow">Stable · private · revocable</p>
      <h1>Your subscription, at one <em>lasting address.</em></h1>
      <p class="lead">Create an opaque subscription URL that survives service restarts and deploys, refreshes from Just My Socks automatically, and stays active until you close it with your private management key.</p>
    </section>

    <div class="grid">
      <section class="card builder" aria-labelledby="builder-title">
        <div class="card-head">
          <div><h2 id="builder-title">Create a permanent link</h2><p>The original credential is encrypted before durable storage.</p></div>
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
          <p class="hint" id="url-hint">Sent only when you test or create. HTTPS protects it in transit; AES-256-GCM protects it at rest.</p>

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
              <span class="field-label">Lifetime</span>
              <div class="info-tile">No automatic expiration</div>
            </div>
          </div>

          <div class="actions">
            <button class="button primary" id="create-link" type="submit" disabled>Create permanent link</button>
            <button class="button secondary" id="check-link" type="button">Test before creating</button>
          </div>
          <p class="status" id="status" role="status" aria-live="polite"></p>
        </form>

        <section class="result" id="result" aria-labelledby="result-label" hidden>
          <label class="field-label" id="result-label" for="output">Your permanent subscription URL</label>
          <textarea id="output" readonly autocomplete="off" spellcheck="false"></textarea>
          <label class="field-label" for="manage-output">Private management key</label>
          <textarea id="manage-output" readonly autocomplete="off" spellcheck="false"></textarea>
          <p class="recovery-note">Save this management key now. It is shown only in this response and is the only way to close the link.</p>
          <p class="result-meta" id="result-meta"></p>
          <div class="actions">
            <button class="button primary" id="copy" type="button">Copy subscription URL</button>
            <button class="button secondary" id="copy-manage" type="button">Copy management key</button>
            <button class="button ghost" id="clear" type="button">Clear sensitive data</button>
          </div>
        </section>
      </section>

      <div>
        <aside class="card aside" aria-labelledby="privacy-title">
          <div class="aside-top">
            <div class="lock" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4.5" y="10" width="15" height="10" rx="3"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10M12 14v2.5"/></svg></div>
            <h2 id="privacy-title">Private by design</h2>
            <p>The public link is opaque. It never exposes the original JMS URL, and its separate management key cannot download the config.</p>
          </div>
          <div class="privacy-list">
            <div class="privacy-item"><span class="check">✓</span><div><strong>No analytics or third-party assets</strong><span>No trackers, fonts, CDNs, or external JavaScript.</span></div></div>
            <div class="privacy-item"><span class="check">✓</span><div><strong>No subscription storage</strong><span>Your link is never written to cookies, localStorage, or sessionStorage. A random HttpOnly device cookie is used only for fair-use limits.</span></div></div>
            <div class="privacy-item"><span class="check">✓</span><div><strong>Encrypted durable registry</strong><span>Original URLs use authenticated encryption; lookup and management tokens are stored only as HMAC digests.</span></div></div>
            <div class="privacy-item"><span class="check">✓</span><div><strong>No shared config caching</strong><span>Rendered proxy credentials are private, non-cacheable, and held in memory only briefly.</span></div></div>
          </div>
        </aside>

        <section class="card howto" aria-labelledby="how-title">
          <h2 id="how-title">Add to Clash Mi</h2>
          <div class="steps">
            <div class="how-step"><span><strong>Paste</strong> the original JMS link above.</span></div>
            <div class="how-step"><span><strong>Create and save</strong> both the subscription URL and private management key.</span></div>
            <div class="how-step"><span>In Clash Mi, open <strong>Profiles / Subscriptions</strong>, add the URL, then update.</span></div>
          </div>
        </section>

        <section class="card manage" aria-labelledby="manage-title">
          <h2 id="manage-title">Close a subscription</h2>
          <p>Closing is permanent: the encrypted original URL is deleted, the subscription URL stops working, and one capacity slot is released.</p>
          <form id="close-form" autocomplete="off" novalidate>
            <label class="field-label" for="manage-key">Private management key</label>
            <input id="manage-key" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="128" placeholder="Paste the saved management key" required>
            <div class="actions"><button class="button danger" type="submit">Permanently close link</button></div>
            <p class="status" id="close-status" role="status" aria-live="polite"></p>
          </form>
        </section>
      </div>
    </div>

    <footer><span>Existing links keep working when creation is full. Availability still depends on this service and the upstream provider remaining active.</span><a href="/health" rel="noreferrer">Service health</a></footer>
  </main>

  <script nonce="__CSP_NONCE__">
    (() => {
      "use strict";
      const form = document.getElementById("builder");
      const source = document.getElementById("source-url");
      const format = document.getElementById("format");
      const reveal = document.getElementById("reveal");
      const result = document.getElementById("result");
      const output = document.getElementById("output");
      const manageOutput = document.getElementById("manage-output");
      const resultMeta = document.getElementById("result-meta");
      const status = document.getElementById("status");
      const capacityBadge = document.getElementById("capacity");
      const createButton = document.getElementById("create-link");
      const checkButton = document.getElementById("check-link");
      const copyButton = document.getElementById("copy");
      const copyManageButton = document.getElementById("copy-manage");
      const clearButton = document.getElementById("clear");
      const closeForm = document.getElementById("close-form");
      const closeKey = document.getElementById("manage-key");
      const closeStatus = document.getElementById("close-status");
      let acceptingNewLinks = false;

      const setStatus = (message, kind = "", target = status) => {
        target.textContent = message;
        target.dataset.kind = kind;
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

      const requestJson = async (path, options = {}) => {
        const response = await fetch(path, {
          credentials: "same-origin",
          cache: "no-store",
          referrerPolicy: "no-referrer",
          ...options
        });
        let payload = {};
        try { payload = await response.json(); } catch (_) { /* generic error below */ }
        if (!response.ok) {
          const error = new Error(payload.message || "The service could not complete this request.");
          error.code = payload.code || "request_failed";
          throw error;
        }
        return payload;
      };

      const loadCapacity = async () => {
        try {
          const payload = await requestJson("/api/capacity");
          acceptingNewLinks = Boolean(payload.enabled && payload.accepting);
          createButton.disabled = !acceptingNewLinks;
          if (!payload.enabled) {
            capacityBadge.textContent = "Permanent links unavailable";
            capacityBadge.dataset.state = "closed";
          } else if (payload.accepting) {
            const noun = payload.remaining === 1 ? "slot" : "slots";
            capacityBadge.textContent = `${payload.remaining} creation ${noun} available`;
            capacityBadge.dataset.state = "open";
          } else {
            capacityBadge.textContent = "Creation full · existing links active";
            capacityBadge.dataset.state = "closed";
          }
        } catch (_) {
          acceptingNewLinks = false;
          createButton.disabled = true;
          capacityBadge.textContent = "Capacity check unavailable";
          capacityBadge.dataset.state = "closed";
        }
      };

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!acceptingNewLinks) {
          setStatus("New link creation is currently full. Existing subscriptions remain active.", "error");
          return;
        }
        let raw = "";
        try { raw = validate(); } catch (error) { setStatus(error.message, "error"); return; }
        createButton.disabled = true;
        checkButton.disabled = true;
        setStatus("Verifying and encrypting your subscription…", "working");
        try {
          const payload = await requestJson("/api/links", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: raw, format: format.value})
          });
          output.value = payload.subscription_url;
          manageOutput.value = payload.manage_key;
          const created = new Date(payload.created_at * 1000).toLocaleString();
          resultMeta.textContent = `${payload.nodes} proxy node${payload.nodes === 1 ? "" : "s"} verified · created ${created} · no automatic expiry`;
          result.hidden = false;
          source.value = "";
          source.type = "password";
          reveal.setAttribute("aria-pressed", "false");
          setStatus("Permanent link created. Save both values below before leaving this page.", "success");
          result.scrollIntoView({behavior: "smooth", block: "nearest"});
        } catch (error) {
          setStatus(error.message || "Permanent link creation failed.", "error");
        } finally {
          raw = "";
          checkButton.disabled = false;
          await loadCapacity();
        }
      });

      reveal.addEventListener("click", () => {
        const showing = source.type === "text";
        source.type = showing ? "password" : "text";
        reveal.setAttribute("aria-pressed", String(!showing));
        reveal.setAttribute("aria-label", showing ? "Show subscription link" : "Hide subscription link");
      });

      const copyValue = async (element) => {
        if (!element.value) return false;
        try {
          await navigator.clipboard.writeText(element.value);
        } catch (_) {
          element.focus();
          element.select();
          document.execCommand("copy");
        }
        return true;
      };

      copyButton.addEventListener("click", async () => {
        if (!await copyValue(output)) return;
        setStatus("Copied. Paste it into Clash Mi → Profiles / Subscriptions.", "success");
      });

      copyManageButton.addEventListener("click", async () => {
        if (!await copyValue(manageOutput)) return;
        setStatus("Management key copied. Store it privately; it can permanently close this link.", "success");
      });

      checkButton.addEventListener("click", async () => {
        let raw = "";
        try { raw = validate(); } catch (error) { setStatus(error.message, "error"); return; }
        checkButton.disabled = true;
        createButton.disabled = true;
        setStatus("Testing the upstream without creating a permanent link…", "working");
        try {
          const payload = await requestJson("/api/check", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: raw, format: format.value, force_refresh: true})
          });
          setStatus(`Connection works — ${payload.nodes} proxy node${payload.nodes === 1 ? "" : "s"} found. Nothing was stored.`, "success");
        } catch (error) {
          setStatus(error.message || "Connection check failed.", "error");
        } finally {
          checkButton.disabled = false;
          createButton.disabled = !acceptingNewLinks;
          raw = "";
        }
      });

      const clearSensitiveData = () => {
        source.value = "";
        source.type = "password";
        output.value = "";
        manageOutput.value = "";
        resultMeta.textContent = "";
        result.hidden = true;
        reveal.setAttribute("aria-pressed", "false");
        setStatus("Sensitive data cleared from this tab.", "success");
        source.focus();
      };

      clearButton.addEventListener("click", clearSensitiveData);

      closeForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        let key = closeKey.value.trim();
        if (!key) {
          setStatus("Paste the private management key first.", "error", closeStatus);
          return;
        }
        if (!window.confirm("Permanently close this subscription link? This cannot be undone.")) return;
        const closeButton = closeForm.querySelector("button[type='submit']");
        closeButton.disabled = true;
        setStatus("Permanently closing the link…", "working", closeStatus);
        try {
          await requestJson("/api/links/close", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({manage_key: key})
          });
          if (manageOutput.value === key) {
            output.value = "";
            manageOutput.value = "";
            resultMeta.textContent = "";
            result.hidden = true;
          }
          closeKey.value = "";
          setStatus("Subscription permanently closed. Its URL no longer works and the slot is available again.", "success", closeStatus);
          await loadCapacity();
        } catch (error) {
          setStatus(error.message || "Could not close the subscription.", "error", closeStatus);
        } finally {
          key = "";
          closeButton.disabled = false;
        }
      });

      window.addEventListener("pagehide", () => {
        source.value = "";
        output.value = "";
        manageOutput.value = "";
        closeKey.value = "";
      });

      loadCapacity();
    })();
  </script>
</body>
</html>
"""
