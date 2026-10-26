from flask import Flask, request, render_template_string, send_file
from difflib import unified_diff
from datetime import datetime
import html, re, uuid
from pathlib import Path

app = Flask(__name__)
REPORT_DIR = Path('/mnt/data')

COMMAND_RE = re.compile(r'^\s*(show\s+.+?)\s*$', re.I)
MARKER_RE = re.compile(r'^=+\s*COMMAND:\s*(show\s+.*?)\s*=+\s*$', re.I)

# Commands where exact text is noisy; these are highlighted as WARNING when changed.
NOISY = ('show interfaces extensive', 'show system uptime', 'show system commit')


def split_commands(text):
    """Split a pasted Junos transcript into {command: output}. Supports plain 'show ...' or markers."""
    sections, current, buf = {}, None, []
    for raw in text.replace('\r\n', '\n').split('\n'):
        marker = MARKER_RE.match(raw)
        command = marker.group(1) if marker else (COMMAND_RE.match(raw).group(1) if COMMAND_RE.match(raw) else None)
        if command:
            if current is not None:
                sections[current] = '\n'.join(buf).strip()
            current, buf = command.strip(), []
        elif current is not None:
            buf.append(raw)
    if current is not None:
        sections[current] = '\n'.join(buf).strip()
    return sections


def compare(pre_text, post_text):
    pre, post = split_commands(pre_text), split_commands(post_text)
    commands = list(dict.fromkeys(list(pre) + list(post)))
    results = []
    for cmd in commands:
        before, after = pre.get(cmd), post.get(cmd)
        if before is None:
            status, reason = 'FAIL', 'Command missing from PRE check'
        elif after is None:
            status, reason = 'FAIL', 'Command missing from POST check'
        elif before == after:
            status, reason = 'PASS', 'No change detected'
        else:
            status = 'WARNING' if cmd.lower().startswith(NOISY) else 'CHANGED'
            reason = 'Output changed; review the detailed diff'
        diff = ''
        if before != after:
            diff = '\n'.join(unified_diff(
                (before or '').splitlines(), (after or '').splitlines(),
                fromfile='PRE', tofile='POST', lineterm=''))
        results.append({'command': cmd, 'status': status, 'reason': reason,
                        'pre': before or '', 'post': after or '', 'diff': diff})
    return results


def make_report(results):
    counts = {s: sum(r['status'] == s for r in results) for s in ('PASS','CHANGED','WARNING','FAIL')}
    rows = []
    for idx, r in enumerate(results, 1):
        rows.append(f'''<div class="item {r['status'].lower()}">
        <button class="summary" onclick="toggle('d{idx}')">
          <span class="badge">{r['status']}</span><strong>{html.escape(r['command'])}</strong>
          <span class="reason">{html.escape(r['reason'])}</span><span class="chev">Details ▾</span>
        </button>
        <div id="d{idx}" class="detail">
          <h4>Unified difference</h4><pre>{html.escape(r['diff'] or 'No difference.')}</pre>
          <div class="columns"><div><h4>PRE</h4><pre>{html.escape(r['pre'])}</pre></div>
          <div><h4>POST</h4><pre>{html.escape(r['post'])}</pre></div></div>
        </div></div>''')
    return REPORT_TMPL.replace('{{GENERATED}}', datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')) \
        .replace('{{COUNTS}}', ''.join(f'<div class="card"><b>{k}</b><span>{v}</span></div>' for k,v in counts.items())) \
        .replace('{{ROWS}}', ''.join(rows))

PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>Junos Pre/Post Comparator</title>
<style>
:root{--blue:#0067b1;--bg:#f5f7fa;--border:#d9e0e7}*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Segoe UI,Arial,sans-serif;color:#17202a}.wrap{max-width:1400px;margin:auto;padding:28px}h1{margin-bottom:6px}.lead{color:#586575;margin-top:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:white;border:1px solid var(--border);border-radius:10px;padding:16px;box-shadow:0 2px 8px #0000000a}textarea{width:100%;height:520px;resize:vertical;border:1px solid #aeb9c4;border-radius:6px;padding:12px;font:13px Consolas,monospace}.actions{display:flex;gap:12px;margin-top:18px;align-items:center}.btn{border:0;border-radius:6px;padding:11px 18px;font-weight:600;cursor:pointer}.primary{background:var(--blue);color:white}.secondary{background:#e8edf3;color:#17202a}input[type=file]{max-width:300px}.hint{font-size:13px;color:#687585} @media(max-width:850px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap"><h1>Junos Pre/Post Check Comparator</h1>
<p class="lead">Paste manually collected PRE and POST Junos <code>show</code> command results, or load two TXT files. The generated HTML report shows a brief status and expandable details.</p>
<form method="post" action="/compare">
<div class="grid"><div class="panel"><h3>PRE check</h3><input type="file" accept=".txt,.log" onchange="loadFile(this,'pre')"><p class="hint">Expected format: each section starts with <b>show ...</b> or <b>===== COMMAND: show ... =====</b>.</p><textarea id="pre" name="pre" placeholder="show interfaces terse\n...\n\nshow bgp summary\n..."></textarea></div>
<div class="panel"><h3>POST check</h3><input type="file" accept=".txt,.log" onchange="loadFile(this,'post')"><p class="hint">Use the same command list as the PRE check for the cleanest comparison.</p><textarea id="post" name="post" placeholder="show interfaces terse\n...\n\nshow bgp summary\n..."></textarea></div></div>
<div class="actions"><button class="btn primary" type="submit">Compare and generate HTML report</button><button class="btn secondary" type="button" onclick="document.getElementById('pre').value='';document.getElementById('post').value=''">Clear</button></div></form></div>
<script>function loadFile(input,target){const f=input.files[0];if(!f)return;const r=new FileReader();r.onload=e=>document.getElementById(target).value=e.target.result;r.readAsText(f)}</script></body></html>'''

REPORT_TMPL = r'''<!doctype html><html><head><meta charset="utf-8"><title>Junos Pre/Post Report</title><style>
body{font-family:Segoe UI,Arial,sans-serif;background:#f5f7fa;color:#17202a;margin:0}.wrap{max-width:1400px;margin:auto;padding:28px}.cards{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.card{background:white;border:1px solid #d9e0e7;border-radius:8px;padding:12px 18px;min-width:120px}.card b{display:block}.card span{font-size:25px}.item{background:white;border:1px solid #d9e0e7;border-left:6px solid #677;margin:10px 0;border-radius:7px;overflow:hidden}.item.pass{border-left-color:#107c10}.item.changed{border-left-color:#d83b01}.item.warning{border-left-color:#ffb900}.item.fail{border-left-color:#a80000}.summary{width:100%;border:0;background:white;padding:14px;text-align:left;display:grid;grid-template-columns:90px 1fr 1fr auto;gap:12px;cursor:pointer;align-items:center}.badge{font-weight:700}.reason{color:#586575}.chev{color:#0067b1}.detail{display:none;padding:0 16px 16px;border-top:1px solid #e3e8ed}.columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}pre{background:#101820;color:#e8edf3;padding:12px;border-radius:6px;overflow:auto;white-space:pre-wrap;font:12px Consolas,monospace}@media(max-width:900px){.summary,.columns{grid-template-columns:1fr}.chev{display:none}}</style></head>
<body><div class="wrap"><h1>Junos PRE/POST Comparison Report</h1><p>Generated {{GENERATED}}</p><div class="cards">{{COUNTS}}</div><h2>Brief report</h2>{{ROWS}}</div>
<script>function toggle(id){const e=document.getElementById(id);e.style.display=e.style.display==='block'?'none':'block'}</script></body></html>'''

@app.get('/')
def home():
    return render_template_string(PAGE)

@app.post('/compare')
def compare_route():
    pre, post = request.form.get('pre',''), request.form.get('post','')
    results = compare(pre, post)
    report = make_report(results)
    name = f"junos_pre_post_report_{uuid.uuid4().hex[:8]}.html"
    path = REPORT_DIR / name
    path.write_text(report, encoding='utf-8')
    return send_file(path, as_attachment=False, download_name=name)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
