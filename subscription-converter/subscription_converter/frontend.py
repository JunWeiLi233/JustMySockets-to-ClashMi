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
  <meta name="color-scheme" content="light">
  <title>JMS Config Bridge — Private subscription converter</title>
  <style nonce="__CSP_NONCE__">
    /*
      v2 visual system: a small network utility, documented like a field manual.
      The intentionally plain surfaces and asymmetric editorial layout replace
      the gradient/glass/card vocabulary common to generated SaaS landing pages.
    */
    :root {
      color-scheme: light;
      --paper: #f1efe8;
      --paper-deep: #e4e0d5;
      --white: #fbfaf6;
      --ink: #17202a;
      --muted: #60645f;
      --faint: #7a7d77;
      --line: #aaa99f;
      --line-dark: #323a40;
      --orange: #d94b2b;
      --orange-soft: #f2d8ce;
      --green: #16624c;
      --red: #9f2f25;
      --amber: #8b5a12;
      --sans: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
      --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }

    * { box-sizing: border-box; }
    html { min-height: 100%; scroll-behavior: smooth; background: var(--paper); }
    body {
      min-height: 100vh;
      margin: 0;
      overflow-x: hidden;
      color: var(--ink);
      font-family: var(--sans);
      background: var(--paper);
    }
    a { color: inherit; }
    button, input, select, textarea { font: inherit; }
    button, select { cursor: pointer; }
    ::selection { color: var(--white); background: var(--orange); }
    .site { position: relative; border-top: 5px solid var(--ink); }
    .wrap { width: min(1180px, calc(100% - 56px)); margin: 0 auto; }

    .topbar {
      display: flex;
      min-height: 72px;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      border-bottom: 1px solid var(--line-dark);
    }
    .brand { display: flex; align-items: baseline; gap: 8px; text-decoration: none; }
    .brand-mark {
      display: inline-block;
      width: auto;
      height: auto;
      border: 0;
      border-radius: 0;
      color: var(--orange);
      box-shadow: none;
      font-family: var(--mono);
      font-size: 15px;
      font-weight: 800;
      letter-spacing: -.04em;
    }
    .brand-mark::after, .brand-mark svg { display: none; }
    .brand-copy { display: flex; align-items: baseline; gap: 11px; }
    .brand-copy strong {
      color: var(--ink);
      font-family: var(--sans);
      font-size: 15px;
      font-weight: 750;
      letter-spacing: -.015em;
    }
    .brand-copy span {
      margin: 0;
      color: var(--faint);
      font-family: var(--mono);
      font-size: 9px;
      letter-spacing: .08em;
    }
    .live { display: inline-flex; align-items: center; gap: 9px; }
    .live-dot {
      width: 6px;
      height: 6px;
      background: var(--green);
      box-shadow: none;
    }
    .capacity {
      padding: 0;
      border: 0;
      border-radius: 0;
      color: var(--muted);
      background: transparent;
      font-size: 9px;
      letter-spacing: .04em;
    }
    .capacity[data-state="open"] { color: var(--green); border: 0; }
    .capacity[data-state="closed"] { color: var(--amber); border: 0; }

    .hero {
      display: grid;
      min-height: 0;
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, .55fr);
      align-items: stretch;
      gap: 0;
      padding: 0;
      border-bottom: 1px solid var(--line-dark);
    }
    .hero-copy {
      padding: clamp(72px, 9vw, 128px) clamp(40px, 8vw, 100px) clamp(70px, 8vw, 108px) 0;
      border-right: 1px solid var(--line-dark);
    }
    .eyebrow, .section-kicker {
      gap: 0;
      margin: 0 0 23px;
      color: var(--orange);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .12em;
    }
    .eyebrow::before, .section-kicker::before { display: none; }
    .hero h1 {
      max-width: 800px;
      margin: 0;
      font-family: var(--serif);
      font-size: clamp(54px, 7.1vw, 96px);
      font-weight: 400;
      letter-spacing: -.052em;
      line-height: .95;
      text-transform: none;
    }
    .lead {
      max-width: 650px;
      margin: 30px 0 0;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.65;
    }
    .hero-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; margin-top: 35px; }
    .link-button {
      display: inline-flex;
      min-height: 44px;
      align-items: center;
      justify-content: center;
      padding: 0 15px;
      border: 1px solid var(--ink);
      border-radius: 2px;
      color: var(--white);
      background: var(--ink);
      box-shadow: none;
      font-size: 10px;
      letter-spacing: .07em;
      transition: color .15s ease, background .15s ease;
    }
    .link-button:hover { transform: none; border-color: var(--orange); background: var(--orange); }
    .link-button.quiet { border-color: var(--line-dark); color: var(--ink); background: transparent; }
    .link-button.quiet:hover { color: var(--white); background: var(--ink); }

    .route-sheet {
      display: flex;
      min-height: 100%;
      flex-direction: column;
      justify-content: space-between;
      padding: 34px 0 34px 34px;
    }
    .route-sheet-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-family: var(--mono);
      font-size: 9px;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .route-sheet-head code { color: var(--orange); font: inherit; }
    .route-sheet dl { margin: 28px 0 auto; }
    .route-sheet dl > div {
      display: grid;
      grid-template-columns: 82px 1fr;
      gap: 14px;
      padding: 13px 0;
      border-bottom: 1px solid #cfccc3;
    }
    .route-sheet dt {
      color: var(--faint);
      font-family: var(--mono);
      font-size: 9px;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    .route-sheet dd { margin: 0; font-family: var(--serif); font-size: 16px; line-height: 1.35; }
    .route-seal {
      margin: 42px 0 0;
      padding-top: 15px;
      border-top: 3px solid var(--orange);
      color: var(--muted);
      font-family: var(--mono);
      font-size: 9px;
      line-height: 1.55;
      text-transform: uppercase;
    }

    .workbench, .protocol, .offboard { padding: clamp(72px, 9vw, 118px) 0; }
    .section-heading {
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr) minmax(260px, 390px);
      align-items: start;
      gap: 28px;
      margin-bottom: 42px;
      padding-top: 16px;
      border-top: 1px solid var(--line-dark);
    }
    .section-number { color: var(--orange); font-family: var(--mono); font-size: 11px; }
    .section-heading h2, .offboard h2 {
      margin: 0;
      font-family: var(--serif);
      font-size: clamp(38px, 5vw, 64px);
      font-weight: 400;
      letter-spacing: -.035em;
      line-height: 1;
      text-transform: none;
    }
    .section-heading > p { margin: 2px 0 0; color: var(--muted); font-size: 14px; line-height: 1.65; }

    .workspace-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.48fr) minmax(280px, .52fr);
      align-items: start;
      gap: 0;
      border: 1px solid var(--line-dark);
      background: var(--white);
    }
    .card {
      border: 0;
      border-radius: 0;
      background: transparent;
      box-shadow: none;
      backdrop-filter: none;
    }
    .builder { padding: clamp(25px, 4vw, 44px); border-right: 1px solid var(--line-dark); }
    .card-head {
      align-items: baseline;
      margin-bottom: 36px;
      padding-bottom: 15px;
      border-bottom: 1px solid var(--line);
    }
    .card-head h2, .aside h2, .howto h2, .manage h2 {
      font-family: var(--sans);
      font-size: 15px;
      font-weight: 750;
      letter-spacing: -.015em;
      text-transform: none;
    }
    .card-head p { color: var(--muted); font-size: 11px; }
    .step {
      display: block;
      min-width: auto;
      height: auto;
      border: 0;
      border-radius: 0;
      color: var(--orange);
      font-size: 9px;
    }
    label.field-label, span.field-label {
      display: block;
      margin-bottom: 8px;
      color: var(--ink);
      font-size: 9px;
      font-weight: 750;
      letter-spacing: .07em;
    }
    .secret-field { position: relative; }
    input[type="password"], input[type="text"], select, textarea {
      width: 100%;
      border: 1px solid #8e918c;
      border-radius: 2px;
      color: var(--ink);
      background: var(--white);
      transition: border-color .15s ease, box-shadow .15s ease;
    }
    input[type="password"], input[type="text"] { min-height: 52px; font-size: 12px; }
    input:focus, select:focus, textarea:focus {
      border-color: var(--ink);
      box-shadow: 0 0 0 3px var(--orange-soft);
      background: #fff;
    }
    .reveal {
      position: absolute;
      top: 7px;
      right: 7px;
      border-radius: 1px;
      color: var(--muted);
    }
    .reveal:hover { color: var(--ink); background: var(--paper-deep); }
    .reveal svg { width: 18px; height: 18px; vertical-align: middle; }
    .hint { color: var(--faint); }
    .options { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 25px; }
    select { min-height: 48px; color: var(--ink); background: var(--white); }
    .info-tile {
      min-height: 48px;
      border: 1px solid #8e918c;
      border-radius: 2px;
      color: var(--muted);
      background: var(--paper);
    }
    .info-tile::before { color: var(--orange); }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 24px; }
    .button {
      display: inline-flex;
      min-height: 43px;
      align-items: center;
      justify-content: center;
      padding: 0 15px;
      border: 1px solid transparent;
      border-radius: 2px;
      font-family: var(--mono);
      font-size: 9px;
      font-weight: 750;
      letter-spacing: .05em;
      text-transform: uppercase;
      box-shadow: none;
      transition: color .15s ease, background .15s ease, border-color .15s ease;
    }
    .button:hover:not(:disabled) { transform: none; }
    .button:disabled { cursor: not-allowed; opacity: .42; }
    .button.primary { color: #fff; background: var(--orange); box-shadow: none; }
    .button.primary:hover:not(:disabled) { background: var(--ink); }
    .button.secondary { border-color: var(--line-dark); color: var(--ink); background: transparent; }
    .button.secondary:hover:not(:disabled) { color: #fff; background: var(--ink); }
    .button.ghost { color: var(--muted); }
    .button.danger { border-color: var(--red); color: var(--red); background: transparent; }
    .button.danger:hover:not(:disabled) { color: #fff; background: var(--red); }
    .status[data-kind="success"] { color: var(--green); }
    .status[data-kind="error"] { color: var(--red); }
    .status[data-kind="working"] { color: var(--amber); }
    .status { min-height: 22px; margin: 15px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .result { margin-top: 28px; padding-top: 25px; border-top: 1px solid var(--line); }
    .result[hidden] { display: none; }
    textarea { min-height: 108px; resize: vertical; padding: 13px; font-family: var(--mono); font-size: 11px; line-height: 1.55; }
    .result .field-label:not(:first-child) { margin-top: 21px; }
    .recovery-note { color: var(--amber); }
    .result-meta { color: var(--faint); font-size: 11px; line-height: 1.55; }

    .work-notes { background: var(--paper-deep); }
    .note-block { padding: 28px; border-bottom: 1px solid var(--line); }
    .note-block:last-child { border-bottom: 0; }
    .note-label {
      display: block;
      margin-bottom: 18px;
      color: var(--orange);
      font-family: var(--mono);
      font-size: 9px;
      font-weight: 750;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .note-block h3 { margin: 0 0 10px; font-family: var(--serif); font-size: 24px; font-weight: 400; line-height: 1.1; }
    .note-block p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.65; }
    .plain-steps { display: grid; gap: 0; margin: 18px 0 0; padding: 0; list-style: none; counter-reset: note-steps; }
    .plain-steps li {
      display: grid;
      grid-template-columns: 24px 1fr;
      gap: 7px;
      padding: 10px 0;
      border-top: 1px solid #c7c3b8;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
      counter-increment: note-steps;
    }
    .plain-steps li::before { color: var(--orange); content: counter(note-steps, decimal-leading-zero); font-family: var(--mono); font-size: 9px; }
    .plain-steps strong { color: var(--ink); }

    .protocol { border-top: 1px solid var(--line-dark); }
    .route-ledger { border-top: 1px solid var(--line-dark); }
    .route-row {
      display: grid;
      grid-template-columns: 74px minmax(150px, .42fr) minmax(0, 1fr) 160px;
      gap: 28px;
      align-items: baseline;
      padding: 23px 0;
      border-bottom: 1px solid var(--line);
    }
    .route-row-num, .route-row-state { color: var(--faint); font-family: var(--mono); font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }
    .route-row h3 { margin: 0; font-family: var(--serif); font-size: 25px; font-weight: 400; }
    .route-row p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .route-row-state { color: var(--green); text-align: right; }
    .privacy-ledger {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0;
      margin-top: 55px;
      border: 1px solid var(--line-dark);
      background: var(--white);
    }
    .privacy-ledger > div { padding: 25px 28px; border-bottom: 1px solid var(--line); }
    .privacy-ledger > div:nth-child(odd) { border-right: 1px solid var(--line); }
    .privacy-ledger > div:nth-last-child(-n+2) { border-bottom: 0; }
    .privacy-ledger strong { display: block; margin-bottom: 7px; font-size: 12px; }
    .privacy-ledger span { color: var(--muted); font-size: 11px; line-height: 1.55; }

    .offboard {
      display: grid;
      grid-template-columns: .75fr 1.25fr;
      align-items: start;
      gap: clamp(35px, 7vw, 92px);
      border-top: 1px solid var(--line-dark);
    }
    .offboard-copy { position: static; }
    .offboard-copy p { margin-top: 20px; font-size: 14px; }
    .manage { padding: clamp(25px, 4vw, 40px); border: 1px solid var(--line-dark); background: var(--white); }
    .manage h2 { margin-bottom: 9px; }
    .manage > p { color: var(--muted); }

    footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 22px 0 34px;
      border-color: var(--line-dark);
      color: var(--faint);
      font-size: 8px;
    }
    footer a { color: var(--ink); }

    @media (max-width: 900px) {
      .hero { grid-template-columns: 1fr; }
      .hero-copy { padding-right: 0; border-right: 0; }
      .route-sheet { padding: 30px 0; border-top: 1px solid var(--line-dark); }
      .workspace-grid { grid-template-columns: 1fr; }
      .builder { border-right: 0; border-bottom: 1px solid var(--line-dark); }
      .work-notes { display: grid; grid-template-columns: 1fr 1fr; }
      .note-block { border-right: 1px solid var(--line); border-bottom: 0; }
      .note-block:last-child { border-right: 0; }
      .section-heading { grid-template-columns: 54px 1fr; }
      .section-heading > p { grid-column: 2; }
      .route-row { grid-template-columns: 54px 160px 1fr; }
      .route-row-state { grid-column: 2; text-align: left; }
    }

    @media (max-width: 640px) {
      .wrap { width: min(100% - 30px, 600px); }
      .topbar { min-height: 64px; }
      .brand-copy span { display: none; }
      .capacity { max-width: 145px; text-align: right; }
      .hero-copy { padding: 62px 0 58px; }
      .hero h1 { font-size: clamp(46px, 14vw, 72px); }
      .lead { font-size: 15px; }
      .hero-actions .link-button { flex: 1 1 100%; }
      .route-sheet dl > div { grid-template-columns: 74px 1fr; }
      .workbench, .protocol, .offboard { padding: 72px 0; }
      .section-heading { grid-template-columns: 38px 1fr; gap: 14px; }
      .section-heading > p { grid-column: 1 / -1; }
      .options, .work-notes, .privacy-ledger { grid-template-columns: 1fr; }
      .note-block { border-right: 0; border-bottom: 1px solid var(--line); }
      .privacy-ledger > div, .privacy-ledger > div:nth-child(odd) { border-right: 0; border-bottom: 1px solid var(--line); }
      .privacy-ledger > div:last-child { border-bottom: 0; }
      .route-row { grid-template-columns: 36px 1fr; gap: 13px; }
      .route-row p { grid-column: 2; }
      .route-row-state { grid-column: 2; }
      .offboard { grid-template-columns: 1fr; }
      .actions .button { flex: 1 1 100%; }
      footer { display: block; }
    }

    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { transition: none !important; }
    }
  </style>
</head>
<body>
  <main class="site">
    <header class="topbar wrap">
      <a class="brand" href="#top" aria-label="JMS Config Bridge home">
        <span class="brand-mark" aria-hidden="true">jms/</span>
        <span class="brand-copy"><strong>Config Bridge</strong><span>Subscription conversion utility</span></span>
      </a>
      <div class="live"><span class="live-dot" aria-hidden="true"></span><span class="capacity" id="capacity" data-state="checking">Checking capacity…</span></div>
    </header>

    <section class="hero wrap" id="top" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Just My Socks subscription converter</p>
        <h1 id="hero-title">A private address for every proxy client.</h1>
        <p class="lead">Give Clash, sing-box, or Surge a stable subscription URL without publishing the source credential. This service fetches the live upstream only when a client asks for it.</p>
        <div class="hero-actions">
          <a class="link-button" href="#converter">Create a private link</a>
          <a class="link-button quiet" href="#protocol">Read the handling notes</a>
        </div>
      </div>

      <aside class="route-sheet" aria-label="Example conversion record">
        <div class="route-sheet-head"><span>Conversion record</span><code>JMS-01</code></div>
        <dl>
          <div><dt>Source</dt><dd>Just My Socks</dd></div>
          <div><dt>Outputs</dt><dd>Mihomo · sing-box · Surge</dd></div>
          <div><dt>Refresh</dt><dd>From upstream, per request</dd></div>
          <div><dt>Public URL</dt><dd>Opaque and revocable</dd></div>
        </dl>
        <p class="route-seal">The source URL is encrypted before durable storage. No analytics, browser storage, fonts, or third-party scripts.</p>
      </aside>
    </section>

    <section class="workbench wrap" id="converter" aria-labelledby="workbench-title">
      <div class="section-heading">
        <span class="section-number">01</span>
        <h2 id="workbench-title">Create a permanent link</h2>
        <p>Paste the source once. Test it if you want, choose the client format, then save both generated values.</p>
      </div>

      <div class="workspace-grid">
        <section class="card builder" aria-labelledby="builder-title">
          <div class="card-head">
            <div><h2 id="builder-title">New subscription route</h2><p>The original credential is encrypted before durable storage.</p></div>
            <span class="step" aria-hidden="true">PRIVATE WORKSPACE</span>
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
              <div><span class="field-label">Lifetime</span><div class="info-tile">No automatic expiration</div></div>
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

        <aside class="work-notes" aria-label="Instructions and privacy notes">
          <div class="note-block">
            <span class="note-label">Before you begin</span>
            <h3>Two values, two jobs.</h3>
            <p>The subscription URL goes into your client. The management key stays with you and can only close the link.</p>
            <ol class="plain-steps">
              <li><span><strong>Paste</strong> the original JMS link.</span></li>
              <li><span><strong>Save</strong> the generated URL and key.</span></li>
              <li><span><strong>Add</strong> the URL in Clash Mi under Profiles / Subscriptions.</span></li>
            </ol>
          </div>
          <div class="note-block">
            <span class="note-label">Browser boundary</span>
            <h3>Nothing secret is kept in this tab.</h3>
            <p>The source does not enter localStorage or sessionStorage. Rendered proxy credentials are private, non-cacheable, and held in memory only briefly.</p>
          </div>
        </aside>
      </div>
    </section>

    <section class="protocol wrap" id="protocol" aria-labelledby="protocol-title">
      <div class="section-heading">
        <span class="section-number">02</span>
        <h2 id="protocol-title">How a request is handled</h2>
        <p>The interface mirrors the service boundary: accept one secret, keep it sealed, and render only the format requested.</p>
      </div>

      <div class="route-ledger" role="list">
        <article class="route-row" role="listitem">
          <span class="route-row-num">01</span><h3>Receive</h3>
          <p>The original HTTPS subscription URL is submitted directly to this service when you test or create a link.</p>
          <span class="route-row-state">Request only</span>
        </article>
        <article class="route-row" role="listitem">
          <span class="route-row-num">02</span><h3>Seal</h3>
          <p>The source URL is protected with authenticated encryption. Public lookup and management tokens are stored as HMAC digests.</p>
          <span class="route-row-state">Encrypted at rest</span>
        </article>
        <article class="route-row" role="listitem">
          <span class="route-row-num">03</span><h3>Fetch</h3>
          <p>When a client follows the public URL, the service downloads the current upstream subscription rather than serving an old shared copy.</p>
          <span class="route-row-state">Fresh upstream</span>
        </article>
        <article class="route-row" role="listitem">
          <span class="route-row-num">04</span><h3>Render</h3>
          <p>Parsed proxy nodes are written as Mihomo, sing-box, or Surge configuration. The requested transport format never changes the source.</p>
          <span class="route-row-state">Client-ready</span>
        </article>
      </div>

      <div class="privacy-ledger" aria-label="Privacy characteristics">
        <div><strong>No analytics or third-party assets</strong><span>No trackers, CDNs, remote fonts, or external JavaScript.</span></div>
        <div><strong>No browser secret storage</strong><span>The source never enters localStorage or sessionStorage.</span></div>
        <div><strong>Separate management authority</strong><span>The management key can close a link, but it cannot download its configuration.</span></div>
        <div><strong>No shared config cache</strong><span>Rendered proxy credentials stay private and non-cacheable.</span></div>
      </div>
    </section>

    <section class="offboard wrap" aria-labelledby="manage-title">
      <div class="offboard-copy">
        <p class="section-kicker">03 / Link retirement</p>
        <h2>Retire a link</h2>
        <p>Use the saved management key when a subscription URL is no longer needed. The encrypted source is deleted and the public address stops working immediately.</p>
      </div>
      <section class="card manage">
        <h2 id="manage-title">Close a subscription</h2>
        <p>This operation is permanent. The management key is the only credential that can authorize it.</p>
        <form id="close-form" autocomplete="off" novalidate>
          <label class="field-label" for="manage-key">Private management key</label>
          <input id="manage-key" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="128" placeholder="Paste the saved management key" required>
          <div class="actions"><button class="button danger" type="submit">Permanently close link</button></div>
          <p class="status" id="close-status" role="status" aria-live="polite"></p>
        </form>
      </section>
    </section>

    <footer class="wrap"><span>Existing routes keep working when creation is full. Availability still depends on this service and the upstream provider.</span><a href="/health" rel="noreferrer">Service health ↗</a></footer>
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
