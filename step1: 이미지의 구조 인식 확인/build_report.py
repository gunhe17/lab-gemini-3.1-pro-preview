#!/usr/bin/env python3.12
"""step1 골격(열린 JSON 트리) 검수용 report.html 생성.

정답(GT) 비교가 아니라, 모델이 그린 열린 구조를 이미지와 나란히 두고 '눈으로' 검수.
inputs/p-NNN.png + outputs/p-NNN.skeleton.json → self-contained report.html
좌: 페이지 탭 + 렌더 PNG / 우: 펼침 가능한 JSON 트리 + 페이지 승인/총평
"""
import base64
import json
import html
from pathlib import Path

HERE = Path(__file__).parent
INPUTS = HERE / "inputs"
OUT = HERE / "outputs"
GT = HERE / "groundtruth"
ORDER = ["p-038", "p-005", "p-011", "p-017", "p-007"]  # 난이도순 L1→L4


def b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()


def esc(x) -> str:
    return html.escape(str(x))


MEAS = {}
_mf = OUT / "_measurements.json"
if _mf.exists():
    MEAS = json.loads(_mf.read_text())


def meas_html(pid: str) -> str:
    m = MEAS.get(pid)
    if not m:
        return ""
    def cell(v):
        return esc("—" if v is None else v)
    rows = [
        ("선언 열수 (declared_columns)", cell(m.get("declared_columns"))),
        ("행 수 (n_rows)", cell(m.get("n_rows"))),
        ("행폭 (colspan 합)", cell(m.get("row_widths"))),
        ("행폭 분포", cell(m.get("row_width_dist"))),
        ("행폭 최빈 / 비율", f'{cell(m.get("row_width_mode"))} / {cell(m.get("row_width_mode_ratio"))}'),
        ("셀 타입 분포", cell(m.get("cell_type_counts"))),
        ("표 노드 수 (table_nodes)", cell(m.get("table_nodes"))),
        ("최대 중첩 깊이", cell(m.get("max_nesting_depth"))),
        ("총 셀 수", cell(m.get("total_cells"))),
        ("토큰 / 비용($)", f'{cell(m.get("usage_total_tokens"))} / {cell(m.get("usage_cost_usd"))}'),
    ]
    body = "".join(f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>' for k, v in rows)
    return f'''<details class="meas" open><summary>측정값 (raw)</summary>
      <table class="scalar"><tbody>{body}</tbody></table></details>'''


def level_of(pid: str) -> str:
    f = GT / f"{pid}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())["_meta"]["level"]
        except Exception:
            pass
    return "?"


def page_section(pid: str, idx: int) -> str:
    img = b64(INPUTS / f"{pid}.png")
    sk = OUT / f"{pid}.skeleton.json"
    if sk.exists():
        d = json.loads(sk.read_text())
        parsed = d.get("parsed")
        usage = d.get("usage", {})
        if parsed is not None:
            tree_json = json.dumps(parsed, ensure_ascii=False, indent=2)
            status = f'<span class="ok-b">parsed ✓</span> · {usage.get("total_tokens","?")}tok · ${usage.get("cost","?")}'
        else:
            tree_json = d.get("raw", "")
            status = '<span class="no-b">JSON 파싱 실패 — raw 표시</span>'
    else:
        tree_json = "(아직 추출 전 — extract_skeleton.py 실행 필요)"
        status = '<span class="no-b">미추출</span>'

    active = " active" if idx == 0 else ""
    return f'''
<section class="page{active}" id="sec-{pid}">
  <div class="img-col"><img src="data:image/png;base64,{img}" alt="{pid}"></div>
  <div class="data-col">
    <div class="badges">
      <span class="lv">{esc(level_of(pid))}</span>
      <span class="pid">{esc(pid)}</span>
      <span class="st">{status}</span>
    </div>
    <div class="treebar">
      <button class="mini" onclick="expand('{pid}',true)">모두 펼침</button>
      <button class="mini" onclick="expand('{pid}',false)">모두 접기</button>
    </div>
    <div class="tree" id="tree-{pid}"></div>
    <script type="application/json" id="json-{pid}">{esc(tree_json)}</script>
    <div class="page-fb">
      <label class="approve"><input type="checkbox"> 이 페이지 구조 승인</label>
      <textarea rows="3" placeholder="구조 수정 지시 (예: '평가소견 셀 안 ①~⑩은 inner table이 아니라 단일 체크행')"></textarea>
    </div>
  </div>
</section>'''


def main() -> None:
    tabs = "".join(
        f'<button class="tab{" active" if i==0 else ""}" data-pid="{p}">'
        f'{p} <em>{esc(level_of(p))}</em></button>'
        for i, p in enumerate(ORDER))
    sections = "".join(page_section(p, i) for i, p in enumerate(ORDER))

    n_done = sum((OUT / f"{p}.skeleton.json").exists() for p in ORDER)
    doc = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>step1 골격(열린 트리) 검수</title>
<style>
:root{{--bg:#0f1115;--card:#1a1d24;--line:#2c313c;--fg:#e6e8ec;--mut:#8b93a1;--ok:#3cb44b;--no:#e6194B;--warn:#f5a623;--key:#7cc7ff;--str:#c3e88d;}}
*{{box-sizing:border-box}}
body{{margin:0;font:14px/1.5 -apple-system,'Apple SD Gothic Neo',sans-serif;background:var(--bg);color:var(--fg)}}
header.top{{padding:12px 18px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:9}}
header.top h1{{margin:0 0 4px;font-size:16px}} header.top .stats{{color:var(--mut);font-size:12px}}
.tabs{{display:flex;gap:6px;padding:10px 18px;flex-wrap:wrap;border-bottom:1px solid var(--line);position:sticky;top:52px;background:var(--bg);z-index:8}}
.tab{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}}
.tab em{{color:var(--warn);font-style:normal;font-size:11px;margin-left:4px}}
.tab.active{{border-color:var(--warn);color:#fff}}
.page{{display:none;grid-template-columns:minmax(380px,1fr) minmax(440px,1fr);gap:18px;padding:18px;align-items:start}}
.page.active{{display:grid}}
.img-col{{position:sticky;top:108px}}
.img-col img{{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}}
.badges{{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}}
.badges span{{font-size:12px;padding:2px 8px;border-radius:6px;border:1px solid var(--line)}}
.badges .lv{{background:#2a2118;color:var(--warn);border-color:#4a3a1f}}
.ok-b{{color:var(--ok)}} .no-b{{color:var(--no)}}
.treebar{{margin-bottom:6px}}
.mini{{background:var(--card);color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:3px 8px;font-size:11px;cursor:pointer;margin-right:4px}}
.tree{{background:#0d0f13;border:1px solid var(--line);border-radius:8px;padding:10px 12px;font:12.5px/1.5 ui-monospace,Menlo,monospace;overflow:auto;max-height:72vh}}
.tree .node{{padding-left:14px;border-left:1px solid #20242c}}
.tree .tog{{cursor:pointer;color:var(--mut);user-select:none}}
.tree .key{{color:var(--key)}} .tree .str{{color:var(--str)}} .tree .num{{color:#f78c6c}} .tree .bool{{color:#c792ea}}
.tree .kind{{display:inline-block;font-size:10px;padding:0 6px;border-radius:5px;margin-left:6px;vertical-align:1px}}
.k-table{{background:#13354a;color:#7cc7ff}} .k-text{{background:#15351c;color:#c3e88d}}
.k-empty{{background:#3a2a14;color:#f5a623}} .k-label{{background:#2a2433;color:#c792ea}}
.collapsed > .children{{display:none}} .collapsed > .tog::before{{content:"▸ "}} .tog::before{{content:"▾ "}}
.leaf .tog::before{{content:""}}
.page-fb{{margin-top:14px}}
.page-fb .approve{{display:block;margin-bottom:6px;cursor:pointer}}
.page-fb textarea{{width:100%;background:#0d0f13;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px}}
.exportbar{{padding:14px 18px;border-top:1px solid var(--line)}}
button.exp{{background:var(--ok);color:#04210a;border:0;border-radius:8px;padding:8px 16px;font-weight:700;cursor:pointer}}
pre#out{{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 18px;display:none}}
</style></head><body>
<header class="top">
  <h1>step1 — 이미지 골격(열린 JSON 트리) 검수</h1>
  <div class="stats">model: google/gemini-3.1-pro-preview · 5장 (L1~L4) · 추출 {n_done}/5 · 정답 비교 아님 — <b>이미지 ↔ 트리 위상 일치</b>만 눈으로 검수</div>
</header>
<div class="tabs">{tabs}</div>
{sections}
<div class="exportbar">
  <button class="exp" onclick="exportFb()">검수 결과 추출</button>
  <span style="color:var(--mut);font-size:12px;margin-left:10px">승인/총평을 JSON으로 뽑아 전달, 또는 저장 후 ‘반영해줘’</span>
</div>
<pre id="out"></pre>
<script>
// kind 추론: 노드 객체의 kind/type 필드 또는 자식 표 유무로 배지 색
function kindOf(v){{
  if(v&&typeof v==='object'){{
    const k=(v.kind||v.type||'').toString().toLowerCase();
    if(k.includes('table'))return'table'; if(k.includes('text'))return'text';
    if(k.includes('empty')||k.includes('input'))return'empty'; if(k.includes('label'))return'label';
  }}
  return null;
}}
function render(v,key){{
  const wrap=document.createElement('div');
  const isObj=v&&typeof v==='object';
  wrap.className='node'+(isObj?'':' leaf');
  const head=document.createElement('div');
  const tog=document.createElement('span');tog.className='tog';
  let label=key!==null?`<span class="key">${{key}}</span>: `:'';
  if(isObj){{
    const kind=kindOf(v);
    const tag=Array.isArray(v)?`[${{v.length}}]`:'{{…}}';
    head.innerHTML=label+`<span class="muted">${{tag}}</span>`+
      (kind?`<span class="kind k-${{kind}}">${{kind}}</span>`:'');
    head.prepend(tog);
    const ch=document.createElement('div');ch.className='children';
    (Array.isArray(v)?v.map((x,i)=>[i,x]):Object.entries(v)).forEach(([k,x])=>ch.appendChild(render(x,k)));
    wrap.appendChild(head);wrap.appendChild(ch);
    tog.onclick=()=>wrap.classList.toggle('collapsed');
  }}else{{
    const cls=typeof v==='number'?'num':typeof v==='boolean'?'bool':'str';
    const disp=typeof v==='string'?`"${{v}}"`:String(v);
    head.innerHTML=label+`<span class="${{cls}}">${{disp.replace(/</g,'&lt;')}}</span>`;
    head.prepend(tog);wrap.appendChild(head);
  }}
  return wrap;
}}
document.querySelectorAll('.tree').forEach(t=>{{
  const pid=t.id.replace('tree-','');
  const raw=document.getElementById('json-'+pid).textContent;
  try{{t.appendChild(render(JSON.parse(raw),null));}}
  catch(e){{t.innerHTML='<span class="no-b">JSON 아님(raw):</span><pre>'+raw.replace(/</g,'&lt;')+'</pre>';}}
}});
function expand(pid,open){{
  document.querySelectorAll('#tree-'+pid+' .node').forEach(n=>{{
    if(n.querySelector(':scope > .children')) n.classList.toggle('collapsed',!open);
  }});
}}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');document.getElementById('sec-'+t.dataset.pid).classList.add('active');
}});
function exportFb(){{
  const res={{}};
  document.querySelectorAll('.page').forEach(sec=>{{
    const pid=sec.id.replace('sec-','');
    const ok=sec.querySelector('.approve input').checked;
    const note=sec.querySelector('.page-fb textarea').value.trim();
    if(ok||note) res[pid]={{approved:ok,note:note||null}};
  }});
  const o=document.getElementById('out');o.style.display='block';
  o.textContent=JSON.stringify(res,null,2);o.scrollIntoView({{behavior:'smooth'}});
}}
</script></body></html>'''
    out = HERE / "report.html"
    out.write_text(doc, encoding="utf-8")
    print(f"✓ {out}  ({len(doc)//1024} KB, 추출 {n_done}/5)")


if __name__ == "__main__":
    main()
