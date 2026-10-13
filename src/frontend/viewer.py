"""Visor interactivo sincronizado (frontend, perfil `frontend`).

Genera un visor HTML autocontenido con layout en dos paneles:

  ┌─────────────────────────────┬──────────────────────────────┐
  │  Barra de progreso (agentes)                              │
  ├─────────────────────────────┼──────────────────────────────┤
  │  Visor multimedia (vídeo)   │  Manual paso a paso          │
  │                             │  (clic → salta al timestamp) │
  └─────────────────────────────┴──────────────────────────────┘

Consume el payload normalizado por ``contract.normalize_grounding`` (un
``VideoGroundingResult`` del agente de Core IA). No requiere ninguna
dependencia externa: genera HTML + CSS + JS plano.

Comportamiento clave (100% cliente, sin backend):
- Clic en un paso del manual => ``video.currentTime = step.timestamp`` y play.
- El paso activo se resalta automáticamente según ``timeupdate``.
- Barra de progreso de agentes actualizable en vivo vía ``window.__viewer``.
"""

from __future__ import annotations

import json
import html as _html

from .contract import AGENT_STAGES

_STYLE = """
:root {
  --bg: #0f1115;
  --panel: #171a21;
  --panel-2: #1e222c;
  --border: #2a2f3a;
  --text: #e6e8ee;
  --muted: #9aa3b2;
  --accent: #4285f4;
  --accent-2: #34a853;
  --warn: #fbbc04;
  --danger: #ea4335;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; }
body {
  background: var(--bg); color: var(--text);
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  display: flex; flex-direction: column; height: 100vh; overflow: hidden;
}

/* --- Barra de progreso de agentes --- */
.progress-bar {
  display: flex; align-items: center;
  padding: 14px 20px; background: var(--panel);
  border-bottom: 1px solid var(--border);
}
.progress-stage {
  display: flex; align-items: center; flex: 1; min-width: 0;
}
.progress-node {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--panel-2); border: 2px solid var(--border);
  font-size: 14px; flex-shrink: 0; transition: all .25s ease;
}
.progress-label {
  margin-left: 8px; font-size: 12.5px; color: var(--muted);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.progress-link {
  flex: 1; height: 3px; background: var(--border);
  margin: 0 6px; border-radius: 2px;
}
.progress-stage:last-child .progress-link { display: none; }
.progress-stage[data-status="running"] .progress-node {
  border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 0 4px rgba(66,133,244,.15); animation: pulse 1.2s infinite;
}
.progress-stage[data-status="done"] .progress-node {
  background: var(--accent-2); border-color: var(--accent-2); color: #fff;
}
.progress-stage[data-status="error"] .progress-node {
  background: var(--danger); border-color: var(--danger); color: #fff;
}
.progress-stage[data-status="done"] .progress-label { color: var(--text); }
.progress-stage[data-status="running"] .progress-label { color: var(--accent); }
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(66,133,244,.35); }
  70% { box-shadow: 0 0 0 7px rgba(66,133,244,0); }
  100% { box-shadow: 0 0 0 0 rgba(66,133,244,0); }
}

/* --- Layout en dos paneles --- */
.viewer {
  display: grid; grid-template-columns: 1.4fr 1fr; flex: 1; min-height: 0;
}
.pane { display: flex; flex-direction: column; min-height: 0; }
.pane-video { border-right: 1px solid var(--border); }
.pane-steps { background: var(--panel); }
.pane-header {
  padding: 12px 18px; font-size: 13px; font-weight: 600;
  letter-spacing: .03em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--border);
}
.video-wrap { flex: 1; display: flex; align-items: center; justify-content: center; padding: 16px; }
video { width: 100%; max-height: 100%; background: #000; border-radius: 8px; }
.steps-list { flex: 1; overflow-y: auto; padding: 8px; }
.step {
  border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px;
  margin-bottom: 8px; cursor: pointer; background: var(--panel-2);
  transition: border-color .15s, background .15s;
}
.step:hover { border-color: var(--accent); }
.step.active { border-color: var(--accent); background: rgba(66,133,244,.10); }
.step-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.step-num {
  background: var(--accent); color: #fff; border-radius: 6px;
  width: 24px; height: 24px; display: flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.step.active .step-num { background: var(--accent-2); }
.step-title { font-size: 14px; font-weight: 600; }
.step-ts {
  margin-left: auto; font-size: 11.5px; color: var(--accent);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  background: rgba(66,133,244,.12); padding: 2px 7px; border-radius: 4px;
  flex-shrink: 0;
}
.step-desc { font-size: 13px; color: var(--muted); line-height: 1.45; }
.step-cmd {
  display: block; background: #0b0d12; color: #9ef2b0;
  padding: 6px 10px; border-radius: 5px; font-size: 12px; margin-top: 8px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; overflow-x: auto;
}
.step-badge {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .04em;
  padding: 2px 7px; border-radius: 4px; margin-left: 8px; flex-shrink: 0;
}
.step-badge.command { background: rgba(52,168,83,.15); color: #81c995; }
.step-badge.error { background: rgba(234,67,53,.15); color: #f28b82; }
.step-badge.configuration { background: rgba(66,133,244,.15); color: #8ab4f8; }
.step-badge.observation { background: rgba(251,188,4,.15); color: #fdd663; }
.step-shot { margin-top: 8px; }
.step-shot img { max-width: 100%; border-radius: 6px; border: 1px solid var(--border); }
.empty { padding: 30px; text-align: center; color: var(--muted); }

@media (max-width: 860px) {
  .viewer { grid-template-columns: 1fr; grid-template-rows: 1fr 1fr; }
  .pane-video { border-right: none; border-bottom: 1px solid var(--border); }
}
"""

_SCRIPT_TEMPLATE = """
(function () {
  var DATA = __PAYLOAD_JSON__;
  var video = document.getElementById('player');
  var listEl = document.getElementById('steps-list');
  var stepEls = [];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  }); }

  function renderSteps() {
    DATA.steps.forEach(function (step, i) {
      var el = document.createElement('div');
      el.className = 'step';
      el.setAttribute('data-ts', step.timestamp_seconds);

      var type = step.action_type || 'unknown';
      var badge = '<span class="step-badge ' + esc(type) + '">' + esc(type) + '</span>';
      var cmd = step.command ? '<code class="step-cmd">' + esc(step.command) + '</code>' : '';
      var shot = step.screenshot
        ? '<div class="step-shot"><img loading="lazy" src="' + esc(step.screenshot) + '" alt="captura"/></div>'
        : '';

      el.innerHTML =
        '<div class="step-head">' +
          '<span class="step-num">' + (step.index || (i + 1)) + '</span>' +
          '<span class="step-title">' + esc(step.title) + '</span>' +
          badge +
          '<span class="step-ts">▶ ' + esc(step.timestamp_label || '') + '</span>' +
        '</div>' +
        '<div class="step-desc">' + esc(step.description || '') + '</div>' +
        cmd + shot;

      el.addEventListener('click', function () { seekTo(step.timestamp_seconds); });
      listEl.appendChild(el);
      stepEls.push(el);
    });
  }

  function seekTo(sec) {
    if (video.readyState === 0) { video.load(); }
    video.currentTime = Math.max(0, Math.min(sec, (video.duration || sec)));
    video.play().catch(function () {});
    setActive(sec);
  }

  function setActive(sec) {
    var idx = -1;
    for (var i = 0; i < DATA.steps.length; i++) {
      if (DATA.steps[i].timestamp_seconds <= sec + 0.6) idx = i; else break;
    }
    stepEls.forEach(function (el, i) { el.classList.toggle('active', i === idx); });
    if (idx >= 0) {
      stepEls[idx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  // Actualización en tiempo real de la barra de progreso de agentes.
  function setAgentStage(id, status, detail) {
    var stage = document.querySelector('.progress-stage[data-id="' + id + '"]');
    if (!stage) return;
    stage.setAttribute('data-status', status || 'pending');
    if (detail != null) {
      var lbl = stage.querySelector('.progress-label');
      if (lbl) lbl.textContent = detail;
    }
  }

  video.addEventListener('timeupdate', function () { setActive(video.currentTime); });

  renderSteps();
  window.__viewer = { seekTo: seekTo, setAgentStage: setAgentStage };
})();
"""


def _render_progress_bar(stages: list) -> str:
    """Genera el HTML de la barra de progreso de agentes (orden canónico)."""
    by_id = {s["id"]: s for s in stages}
    canonical = {x["id"]: x for x in AGENT_STAGES}
    ordered = []
    for stage in AGENT_STAGES:
        s = by_id.get(stage["id"], {"id": stage["id"], "status": "pending", "detail": ""})
        ordered.append(s)

    parts = ['<div class="progress-bar">']
    n = len(ordered)
    for i, s in enumerate(ordered):
        status = s.get("status", "pending")
        canon = canonical.get(s["id"], {})
        icon = canon.get("icon", "")
        label = _html.escape(canon.get("label", s["id"]))
        parts.append(
            f'<div class="progress-stage" data-status="{_html.escape(status, quote=True)}" '
            f'data-id="{_html.escape(s["id"], quote=True)}">'
            f'<div class="progress-node">{icon}</div>'
            f'<div class="progress-label">{label}</div>'
        )
        if i < n - 1:
            parts.append('<div class="progress-link"></div>')
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def render_viewer_html(payload: dict, stages: list | None = None) -> str:
    """Devuelve un documento HTML completo autocontenido con el visor.

    Args:
        payload: salida de ``contract.normalize_grounding`` (dict con ``title``,
            ``summary``, ``video_src``, ``duration_seconds``, ``steps``).
        stages: lista de dicts ``{id, status, detail}`` (opcional). Si se omite,
            la barra de progreso se pinta en estado 'pending'.
    """
    stages = stages or [{"id": s["id"], "status": "pending", "detail": ""} for s in AGENT_STAGES]
    progress_html = _render_progress_bar(stages)

    payload_json = json.dumps(payload, ensure_ascii=False)
    script = _SCRIPT_TEMPLATE.replace("__PAYLOAD_JSON__", payload_json)

    title = _html.escape(payload.get("title") or "Visor de manual")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>{_STYLE}</style>
</head>
<body>
{progress_html}
<div class="viewer">
  <section class="pane pane-video">
    <div class="pane-header">🎬 Vídeo fuente</div>
    <div class="video-wrap">
      <video id="player" controls preload="metadata" src="{_html.escape(payload.get('video_src') or '', quote=True)}"></video>
    </div>
  </section>
  <section class="pane pane-steps">
    <div class="pane-header">📖 Manual paso a paso <span style="text-transform:none;font-weight:400">(clic para saltar)</span></div>
    <div class="steps-list" id="steps-list"></div>
  </section>
</div>
<script>{script}</script>
</body>
</html>"""


def render_viewer_file(payload: dict, stages: list | None = None) -> str:
    """Alias: devuelve el HTML (para escribir a fichero)."""
    return render_viewer_html(payload, stages=stages)
