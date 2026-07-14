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
      --ink: #fbf7ff;
      --muted: #b9b2cb;
      --faint: #777087;
      --void: #070311;
      --panel: rgba(13, 8, 28, 0.9);
      --panel-strong: #100923;
      --line: rgba(229, 220, 255, 0.16);
      --pink: #ff4fc8;
      --blue: #6a7cff;
      --acid: #dbff71;
      --amber: #ffc56d;
      --danger: #ff829f;
      --display: Impact, Haettenschweiler, "Arial Narrow Bold", "Arial Black", sans-serif;
      --sans: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --shadow: 0 34px 90px rgba(0, 0, 0, 0.55);
    }

    * { box-sizing: border-box; }
    html { min-height: 100%; scroll-behavior: smooth; background: var(--void); }

    body {
      min-height: 100vh;
      margin: 0;
      overflow-x: hidden;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(circle at 72% 5%, rgba(79, 87, 255, 0.34), transparent 30rem),
        radial-gradient(circle at 20% 18%, rgba(255, 54, 188, 0.22), transparent 34rem),
        linear-gradient(180deg, #0b0419 0%, #05020c 58%, #080311 100%);
    }

    body::before {
      position: fixed;
      z-index: -1;
      inset: 0;
      pointer-events: none;
      content: "";
      opacity: 0.2;
      background-image:
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
      background-size: 64px 64px;
      mask-image: linear-gradient(to bottom, black, transparent 80%);
    }

    body::after {
      position: fixed;
      z-index: 10;
      inset: 0;
      pointer-events: none;
      content: "";
      border: 1px solid rgba(255,255,255,.06);
      box-shadow: inset 0 0 120px rgba(0,0,0,.28);
    }

    a { color: inherit; }
    button, input, select, textarea { font: inherit; }
    button, select { cursor: pointer; }

    .site { position: relative; }
    .wrap { width: min(1240px, calc(100% - 48px)); margin: 0 auto; }

    .topbar {
      display: flex;
      min-height: 92px;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      border-bottom: 1px solid rgba(255,255,255,.08);
    }

    .brand { display: flex; align-items: center; gap: 13px; text-decoration: none; }
    .brand-mark {
      position: relative;
      display: grid;
      width: 46px;
      height: 46px;
      place-items: center;
      border: 1px solid rgba(255,79,200,.7);
      border-radius: 50%;
      color: var(--ink);
      box-shadow: 0 0 24px rgba(255,79,200,.24), inset 0 0 20px rgba(106,124,255,.14);
    }
    .brand-mark::after { position: absolute; inset: 6px; content: ""; border: 1px solid rgba(106,124,255,.72); border-radius: 50%; }
    .brand-mark svg { z-index: 1; width: 20px; height: 20px; }
    .brand-copy strong { display: block; font-family: var(--display); font-size: 18px; letter-spacing: .035em; }
    .brand-copy span { display: block; margin-top: 2px; color: var(--faint); font-family: var(--mono); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }

    .live { display: inline-flex; align-items: center; gap: 10px; }
    .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--acid); box-shadow: 0 0 16px rgba(219,255,113,.8); }
    .capacity {
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: rgba(5,2,12,.64);
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    .capacity[data-state="open"] { color: var(--acid); border-color: rgba(219,255,113,.42); }
    .capacity[data-state="closed"] { color: var(--amber); border-color: rgba(255,197,109,.38); }

    .hero {
      display: grid;
      min-height: calc(100vh - 92px);
      grid-template-columns: minmax(0, 1.05fr) minmax(430px, .95fr);
      align-items: center;
      gap: clamp(30px, 5vw, 80px);
      padding: 70px 0 88px;
    }
    .hero-copy { position: relative; z-index: 2; }
    .eyebrow, .section-kicker {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin: 0 0 22px;
      color: var(--acid);
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 760;
      letter-spacing: .16em;
      text-transform: uppercase;
    }
    .eyebrow::before, .section-kicker::before { width: 28px; height: 1px; content: ""; background: currentColor; }

    h1 {
      max-width: 750px;
      margin: 0;
      font-family: var(--display);
      font-size: clamp(74px, 9.3vw, 142px);
      font-weight: 900;
      letter-spacing: -.055em;
      line-height: .78;
      text-transform: uppercase;
    }
    h1 span {
      color: transparent;
      -webkit-text-stroke: 1px rgba(251,247,255,.82);
      text-shadow: 0 0 42px rgba(106,124,255,.2);
    }
    .lead { max-width: 620px; margin: 32px 0 0; color: var(--muted); font-size: clamp(16px, 1.8vw, 20px); line-height: 1.6; }
    .hero-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 34px; }

    .link-button {
      display: inline-flex;
      min-height: 50px;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 0 19px;
      border: 1px solid rgba(255,79,200,.62);
      border-radius: 999px;
      color: var(--ink);
      background: rgba(7,3,17,.78);
      box-shadow: 0 0 28px rgba(255,79,200,.13);
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .08em;
      text-decoration: none;
      text-transform: uppercase;
      transition: transform .2s ease, border-color .2s ease, background .2s ease;
    }
    .link-button:hover { transform: translateY(-2px); border-color: var(--pink); background: rgba(255,79,200,.08); }
    .link-button.quiet { border-color: var(--line); color: var(--muted); box-shadow: none; }

    .signal-stage { position: relative; min-height: 620px; isolation: isolate; }
    .signal-stage::before { position: absolute; inset: 8% -16%; z-index: -1; content: ""; border-radius: 50%; background: radial-gradient(circle, rgba(113,61,255,.32), rgba(255,79,200,.12) 34%, transparent 68%); filter: blur(12px); }
    .signal-core {
      position: absolute;
      top: 50%;
      left: 50%;
      width: clamp(280px, 32vw, 430px);
      aspect-ratio: 1;
      transform: translate(-50%, -50%) rotate(-12deg);
      border: 22px solid #05020b;
      border-radius: 50%;
      background: radial-gradient(circle at 36% 30%, #ff58cf 0 7%, #5620a5 36%, #120726 66%);
      box-shadow: -24px -10px 48px rgba(255,70,195,.24), 24px 28px 60px rgba(25,77,255,.3), inset -18px -24px 46px rgba(0,0,0,.62), inset 14px 10px 28px rgba(255,255,255,.12);
    }
    .signal-core::before { position: absolute; inset: 17%; content: ""; border: 3px solid rgba(5,2,11,.72); border-radius: 38% 62% 55% 45%; transform: rotate(40deg); box-shadow: inset 0 0 28px rgba(0,0,0,.42); }
    .signal-core::after { position: absolute; top: 41%; left: 35%; width: 30%; height: 18%; content: ""; border-radius: 999px 999px 45% 45%; background: #080310; box-shadow: 0 0 0 13px rgba(5,2,11,.48); transform: rotate(16deg); }
    .core-ring { position: absolute; inset: -42px; border: 1px solid rgba(106,124,255,.38); border-radius: 50%; animation: orbit 18s linear infinite; }
    .core-ring::before { position: absolute; top: 18%; left: 3%; width: 8px; height: 8px; content: ""; border-radius: 50%; background: var(--acid); box-shadow: 0 0 18px rgba(219,255,113,.8); }
    .core-ring.two { inset: -76px; border-color: rgba(255,79,200,.24); animation-duration: 26s; animation-direction: reverse; }
    .core-ring.two::before { top: auto; right: 9%; bottom: 9%; left: auto; background: var(--pink); box-shadow: 0 0 18px rgba(255,79,200,.78); }

    .signal-card {
      position: absolute;
      z-index: 2;
      min-width: 180px;
      padding: 16px;
      border: 1px solid transparent;
      border-radius: 18px;
      background: linear-gradient(#0a0616, #0a0616) padding-box, linear-gradient(120deg, var(--pink), rgba(106,124,255,.8), rgba(219,255,113,.6)) border-box;
      box-shadow: 0 20px 54px rgba(0,0,0,.38), 0 0 26px rgba(106,124,255,.1);
      backdrop-filter: blur(18px);
    }
    .signal-card strong { display: block; font-family: var(--mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
    .signal-card small { display: block; margin-top: 7px; color: var(--faint); font-family: var(--mono); font-size: 9px; text-transform: uppercase; }
    .signal-card .meter { display: flex; align-items: end; gap: 4px; height: 28px; margin-top: 13px; }
    .signal-card .meter i { display: block; width: 8px; border-radius: 3px 3px 0 0; background: linear-gradient(var(--pink), var(--blue)); }
    .signal-card .meter i:nth-child(1) { height: 30%; } .signal-card .meter i:nth-child(2) { height: 62%; } .signal-card .meter i:nth-child(3) { height: 44%; } .signal-card .meter i:nth-child(4) { height: 88%; } .signal-card .meter i:nth-child(5) { height: 70%; }
    .signal-card.route { top: 10%; right: 0; animation: drift 6s ease-in-out infinite; }
    .signal-card.vault { bottom: 12%; left: -2%; animation: drift 7s ease-in-out -2s infinite; }
    .signal-card.protocols { right: 3%; bottom: 8%; animation: drift 8s ease-in-out -4s infinite; }
    .protocol-row { display: flex; gap: 6px; margin-top: 12px; }
    .protocol-row span { padding: 5px 7px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-family: var(--mono); font-size: 8px; }

    .marquee { overflow: hidden; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); background: rgba(255,255,255,.018); }
    .marquee-track { display: flex; width: max-content; gap: 42px; padding: 17px 0; color: var(--faint); font-family: var(--mono); font-size: 10px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; animation: marquee 28s linear infinite; }
    .marquee-track span::before { margin-right: 42px; color: var(--pink); content: "✦"; }

    .manifesto { padding: 132px 0 116px; }
    .manifesto-head { display: grid; grid-template-columns: 1.25fr .75fr; align-items: end; gap: 50px; margin-bottom: 54px; }
    .manifesto h2, .workbench-title, .offboard h2 { margin: 0; font-family: var(--display); font-size: clamp(54px, 7vw, 98px); letter-spacing: -.04em; line-height: .9; text-transform: uppercase; }
    .manifesto-head > p { margin: 0; color: var(--muted); line-height: 1.7; }
    .feature-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }
    .feature-card {
      position: relative;
      min-height: 310px;
      overflow: hidden;
      padding: clamp(25px, 4vw, 42px);
      border: 1px solid transparent;
      border-radius: 26px;
      background: linear-gradient(145deg, rgba(13,8,28,.97), rgba(7,3,17,.97)) padding-box, linear-gradient(135deg, rgba(255,79,200,.85), rgba(106,124,255,.72), rgba(255,255,255,.1)) border-box;
      box-shadow: var(--shadow);
    }
    .feature-card.wide { grid-column: 1 / -1; min-height: 280px; }
    .feature-card::after { position: absolute; right: -80px; bottom: -110px; width: 260px; height: 260px; content: ""; border-radius: 50%; background: radial-gradient(circle, rgba(106,124,255,.32), transparent 67%); filter: blur(4px); }
    .feature-num { display: block; color: var(--acid); font-family: var(--mono); font-size: 10px; letter-spacing: .12em; }
    .feature-card h3 { max-width: 480px; margin: 72px 0 14px; font-family: var(--display); font-size: clamp(34px, 4vw, 56px); letter-spacing: -.025em; line-height: .95; text-transform: uppercase; }
    .feature-card p { max-width: 520px; margin: 0; color: var(--muted); line-height: 1.65; }
    .feature-card.wide h3 { margin-top: 50px; }
    .feature-chip { position: absolute; top: 32px; right: 32px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 999px; color: var(--faint); font-family: var(--mono); font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }

    .workbench { padding: 92px 0 126px; }
    .workbench-intro { display: flex; align-items: end; justify-content: space-between; gap: 40px; margin-bottom: 44px; }
    .workbench-intro p { max-width: 430px; margin: 0; color: var(--muted); line-height: 1.7; }
    .grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(300px, .75fr); gap: 18px; align-items: start; }
    .card {
      border: 1px solid transparent;
      border-radius: 26px;
      background: linear-gradient(var(--panel), var(--panel)) padding-box, linear-gradient(130deg, rgba(255,79,200,.62), rgba(106,124,255,.56), rgba(255,255,255,.08)) border-box;
      box-shadow: var(--shadow);
      backdrop-filter: blur(20px);
    }
    .builder { padding: clamp(23px, 4vw, 42px); }
    .card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 34px; }
    h2 { margin: 0; font-family: var(--display); font-size: 29px; letter-spacing: -.015em; text-transform: uppercase; }
    .card-head p { margin: 7px 0 0; color: var(--faint); font-size: 13px; }
    .step { display: grid; min-width: 38px; height: 38px; place-items: center; border: 1px solid rgba(219,255,113,.44); border-radius: 50%; color: var(--acid); font-family: var(--mono); font-size: 10px; }

    label.field-label, span.field-label { display: block; margin-bottom: 10px; color: #ddd5ee; font-family: var(--mono); font-size: 10px; font-weight: 760; letter-spacing: .07em; text-transform: uppercase; }
    .secret-field { position: relative; }
    input[type="password"], input[type="text"], select, textarea { width: 100%; border: 1px solid rgba(224,213,255,.18); border-radius: 13px; outline: none; color: var(--ink); background: rgba(3,1,9,.76); transition: border-color .18s ease, box-shadow .18s ease, background .18s ease; }
    input[type="password"], input[type="text"] { min-height: 56px; padding: 0 56px 0 16px; font-family: var(--mono); font-size: 12px; }
    input:focus, select:focus, textarea:focus { border-color: rgba(255,79,200,.78); box-shadow: 0 0 0 4px rgba(255,79,200,.09), 0 0 26px rgba(106,124,255,.08); background: rgba(7,3,17,.94); }
    .reveal { position: absolute; top: 9px; right: 9px; width: 38px; height: 38px; border: 0; border-radius: 10px; color: var(--muted); background: transparent; }
    .reveal:hover { color: var(--ink); background: rgba(255,255,255,.06); }
    .reveal svg { width: 18px; height: 18px; vertical-align: middle; }
    .hint { margin: 9px 0 0; color: var(--faint); font-size: 11px; line-height: 1.55; }
    .options { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 24px; }
    select { min-height: 50px; padding: 0 40px 0 14px; }
    .info-tile { display: flex; min-height: 50px; align-items: center; gap: 11px; padding: 0 14px; border: 1px solid rgba(224,213,255,.14); border-radius: 13px; color: var(--muted); background: rgba(3,1,9,.46); font-size: 12px; }
    .info-tile::before { color: var(--acid); content: "∞"; font-size: 18px; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 25px; }
    .button { min-height: 48px; padding: 0 18px; border: 1px solid transparent; border-radius: 999px; font-family: var(--mono); font-size: 10px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; transition: transform .16s ease, border-color .16s ease, background .16s ease, opacity .16s ease; }
    .button:hover:not(:disabled) { transform: translateY(-2px); }
    .button:disabled { cursor: not-allowed; opacity: .38; }
    .button.primary { color: #090312; background: var(--acid); box-shadow: 0 12px 34px rgba(219,255,113,.14); }
    .button.primary:hover:not(:disabled) { background: #e8ff9e; }
    .button.secondary { border-color: rgba(255,79,200,.48); color: var(--ink); background: rgba(255,79,200,.04); }
    .button.ghost { padding: 0 12px; color: var(--faint); background: transparent; }
    .button.danger { border-color: rgba(255,130,159,.42); color: #ffd1dc; background: rgba(255,130,159,.07); }
    .button.danger:hover:not(:disabled) { background: rgba(255,130,159,.13); }
    .status { min-height: 22px; margin: 15px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .status[data-kind="success"] { color: var(--acid); } .status[data-kind="error"] { color: var(--danger); } .status[data-kind="working"] { color: var(--amber); }
    .result { margin-top: 28px; padding-top: 25px; border-top: 1px solid var(--line); }
    .result[hidden] { display: none; }
    textarea { min-height: 112px; resize: vertical; padding: 14px; font-family: var(--mono); font-size: 11px; line-height: 1.55; }
    .result .field-label:not(:first-child) { margin-top: 22px; }
    .recovery-note { margin: 9px 0 0; color: var(--amber); font-size: 11px; line-height: 1.55; }
    .result-meta { margin: 10px 0 0; color: var(--faint); font-size: 11px; line-height: 1.55; }

    .side-stack { display: grid; gap: 18px; }
    .aside { overflow: hidden; }
    .aside-top { padding: 28px; border-bottom: 1px solid var(--line); background: radial-gradient(circle at 90% 0, rgba(106,124,255,.2), transparent 54%); }
    .lock { display: grid; width: 45px; height: 45px; margin-bottom: 19px; place-items: center; border: 1px solid rgba(255,79,200,.34); border-radius: 50%; color: var(--pink); background: rgba(255,79,200,.07); box-shadow: 0 0 24px rgba(255,79,200,.1); }
    .lock svg { width: 21px; height: 21px; }
    .aside h2 { font-size: 31px; }
    .aside-top p { margin: 10px 0 0; color: var(--muted); font-size: 12px; line-height: 1.65; }
    .privacy-list { display: grid; padding: 6px 28px 17px; }
    .privacy-item { display: grid; grid-template-columns: 23px 1fr; gap: 10px; padding: 16px 0; border-bottom: 1px solid rgba(224,213,255,.08); }
    .privacy-item:last-child { border-bottom: 0; }
    .check { color: var(--acid); font-family: var(--mono); font-weight: 800; }
    .privacy-item strong { display: block; margin-bottom: 4px; font-size: 12px; }
    .privacy-item span { display: block; color: var(--faint); font-size: 11px; line-height: 1.55; }
    .howto { padding: 26px 28px; }
    .howto h2 { margin-bottom: 20px; }
    .steps { display: grid; gap: 15px; counter-reset: steps; }
    .how-step { display: grid; grid-template-columns: 29px 1fr; gap: 10px; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .how-step::before { display: grid; width: 25px; height: 25px; place-items: center; border: 1px solid rgba(106,124,255,.38); border-radius: 50%; color: var(--pink); content: counter(steps); counter-increment: steps; font-family: var(--mono); font-size: 9px; }
    .how-step strong { color: var(--ink); }

    .offboard { display: grid; grid-template-columns: .8fr 1.2fr; align-items: start; gap: clamp(35px, 7vw, 100px); padding: 0 0 120px; }
    .offboard-copy { position: sticky; top: 40px; }
    .offboard-copy p { max-width: 430px; margin: 24px 0 0; color: var(--muted); line-height: 1.7; }
    .manage { padding: clamp(25px, 4vw, 42px); }
    .manage h2 { margin-bottom: 10px; }
    .manage > p { margin: 0 0 22px; color: var(--muted); font-size: 12px; line-height: 1.65; }

    footer { display: flex; justify-content: space-between; gap: 24px; padding: 30px 0 44px; border-top: 1px solid var(--line); color: var(--faint); font-family: var(--mono); font-size: 9px; line-height: 1.6; text-transform: uppercase; }
    footer a { color: var(--muted); text-underline-offset: 4px; }

    @keyframes orbit { to { transform: rotate(360deg); } }
    @keyframes drift { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
    @keyframes marquee { to { transform: translateX(-50%); } }

    @media (max-width: 980px) {
      .hero { grid-template-columns: 1fr; padding-top: 78px; }
      .signal-stage { min-height: 560px; }
      .manifesto-head, .offboard { grid-template-columns: 1fr; }
      .offboard-copy { position: static; }
      .grid { grid-template-columns: 1fr; }
      .side-stack { grid-template-columns: 1fr 1fr; }
      .aside { grid-column: 1 / -1; }
    }

    @media (max-width: 700px) {
      .wrap { width: min(100% - 26px, 620px); }
      .topbar { min-height: 78px; }
      .brand-copy span { display: none; }
      .capacity { max-width: 170px; text-align: center; }
      .hero { min-height: auto; padding: 72px 0 64px; }
      h1 { font-size: clamp(64px, 23vw, 105px); }
      .signal-stage { min-height: 480px; }
      .signal-core { width: min(68vw, 330px); border-width: 16px; }
      .signal-card { min-width: 148px; padding: 13px; }
      .signal-card.route { top: 4%; right: 0; }
      .signal-card.vault { bottom: 4%; left: 0; }
      .signal-card.protocols { right: 0; bottom: 0; }
      .manifesto { padding: 94px 0 80px; }
      .manifesto-head { margin-bottom: 34px; }
      .feature-grid, .side-stack { grid-template-columns: 1fr; }
      .feature-card.wide, .aside { grid-column: auto; }
      .workbench { padding: 70px 0 90px; }
      .workbench-intro { display: block; }
      .workbench-intro p { margin-top: 20px; }
      .options { grid-template-columns: 1fr; }
      .offboard { padding-bottom: 86px; }
      footer { display: block; }
      footer span { display: block; margin-bottom: 8px; }
    }

    @media (max-width: 460px) {
      .brand-mark { width: 40px; height: 40px; }
      .live-dot { display: none; }
      .capacity { max-width: 142px; padding: 8px 10px; font-size: 8px; }
      .hero-actions .link-button { flex: 1 1 100%; }
      .signal-stage { min-height: 430px; }
      .signal-card.protocols { display: none; }
      .builder, .manage { padding: 22px 17px; }
      .actions .button { flex: 1 1 100%; }
    }

    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { animation: none !important; transition: none !important; }
    }
  </style>
</head>
<body>
  <main class="site">
    <header class="topbar wrap">
      <a class="brand" href="#top" aria-label="JMS Config Bridge home">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8.5 15.5 15.5 8.5M7 7h.01M17 17h.01"/><rect x="3" y="3" width="18" height="18" rx="6"/></svg>
        </span>
        <span class="brand-copy"><strong>JMS Config Bridge</strong><span>Private signal router</span></span>
      </a>
      <div class="live"><span class="live-dot" aria-hidden="true"></span><span class="capacity" id="capacity" data-state="checking">Checking capacity…</span></div>
    </header>

    <section class="hero wrap" id="top" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Private signal router · JMS → client</p>
        <h1 id="hero-title">One link.<br><span>Any client.</span></h1>
        <p class="lead">Route one encrypted Just My Socks subscription into the format your client understands. The public address stays stable; the credential behind it stays private.</p>
        <div class="hero-actions">
          <a class="link-button" href="#converter">Build your route <span aria-hidden="true">↘</span></a>
          <a class="link-button quiet" href="#protocol">See the protocol</a>
        </div>
      </div>

      <div class="signal-stage" aria-label="A private subscription moving through the converter">
        <div class="signal-core" aria-hidden="true"><span class="core-ring"></span><span class="core-ring two"></span></div>
        <div class="signal-card route" aria-hidden="true">
          <strong>Route online</strong><small>JMS → Mihomo</small>
          <span class="meter"><i></i><i></i><i></i><i></i><i></i></span>
        </div>
        <div class="signal-card vault" aria-hidden="true"><strong>Vault sealed</strong><small>AES-256-GCM · opaque ID</small></div>
        <div class="signal-card protocols" aria-hidden="true"><strong>Client outputs</strong><span class="protocol-row"><span>CLASH</span><span>SING</span><span>SURGE</span></span></div>
      </div>
    </section>

    <div class="marquee" aria-hidden="true">
      <div class="marquee-track">
        <span>No analytics</span><span>Opaque public links</span><span>Encrypted at rest</span><span>Revocable by key</span><span>Live upstream refresh</span><span>No analytics</span><span>Opaque public links</span><span>Encrypted at rest</span><span>Revocable by key</span><span>Live upstream refresh</span>
      </div>
    </div>

    <section class="manifesto wrap" id="protocol" aria-labelledby="protocol-title">
      <div class="manifesto-head">
        <div>
          <p class="section-kicker">The protocol</p>
          <h2 id="protocol-title">Your subscription should travel, not leak.</h2>
        </div>
        <p>Designed around a simple contract: preserve the source, translate only when requested, and give control back to the person who created the route.</p>
      </div>

      <div class="feature-grid">
        <article class="feature-card">
          <span class="feature-num">01 / SEAL</span><span class="feature-chip">Private at rest</span>
          <h3>Encrypt the source.</h3>
          <p>Your original subscription URL is protected with authenticated encryption before durable storage. Public lookup tokens stay opaque.</p>
        </article>
        <article class="feature-card">
          <span class="feature-num">02 / TRANSLATE</span><span class="feature-chip">Fresh on request</span>
          <h3>Speak every client.</h3>
          <p>Fetch the live upstream and render Clash / Mihomo, sing-box, or Surge without coupling parser logic to the output format.</p>
        </article>
        <article class="feature-card wide">
          <span class="feature-num">03 / CONTROL</span><span class="feature-chip">Your key, your route</span>
          <h3>Revoke without exposing.</h3>
          <p>A separate management key closes the route permanently. It cannot download the config, and the public subscription URL cannot manage itself.</p>
        </article>
      </div>
    </section>

    <section class="workbench wrap" id="converter" aria-labelledby="workbench-title">
      <div class="workbench-intro">
        <div><p class="section-kicker">Signal console</p><h2 class="workbench-title" id="workbench-title">Build the route.</h2></div>
        <p>Paste once, test the upstream, then mint a lasting address. The page keeps no subscription secret in browser storage.</p>
      </div>

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

        <div class="side-stack">
          <aside class="card aside" aria-labelledby="privacy-title">
            <div class="aside-top">
              <div class="lock" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4.5" y="10" width="15" height="10" rx="3"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10M12 14v2.5"/></svg></div>
              <h2 id="privacy-title">Private by design</h2>
              <p>The public link is opaque. It never exposes the original JMS URL, and its separate management key cannot download the config.</p>
            </div>
            <div class="privacy-list">
              <div class="privacy-item"><span class="check">✓</span><div><strong>No analytics or third-party assets</strong><span>No trackers, fonts, CDNs, or external JavaScript.</span></div></div>
              <div class="privacy-item"><span class="check">✓</span><div><strong>No browser secret storage</strong><span>The source never enters localStorage or sessionStorage. A random HttpOnly cookie is used only for fair-use limits.</span></div></div>
              <div class="privacy-item"><span class="check">✓</span><div><strong>Encrypted durable registry</strong><span>Original URLs use authenticated encryption; lookup and management tokens are HMAC digests.</span></div></div>
              <div class="privacy-item"><span class="check">✓</span><div><strong>No shared config caching</strong><span>Rendered proxy credentials are private, non-cacheable, and held in memory only briefly.</span></div></div>
            </div>
          </aside>

          <section class="card howto" aria-labelledby="how-title">
            <h2 id="how-title">Add to Clash Mi</h2>
            <div class="steps">
              <div class="how-step"><span><strong>Paste</strong> the original JMS link in the console.</span></div>
              <div class="how-step"><span><strong>Create and save</strong> both generated values.</span></div>
              <div class="how-step"><span>In Clash Mi, add the URL under <strong>Profiles / Subscriptions</strong>.</span></div>
            </div>
          </section>
        </div>
      </div>
    </section>

    <section class="offboard wrap" aria-labelledby="manage-title">
      <div class="offboard-copy">
        <p class="section-kicker">Exit route</p>
        <h2>Close the signal.</h2>
        <p>Control includes a clean ending. Closing deletes the encrypted source, stops the public route, and immediately releases its capacity slot.</p>
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
