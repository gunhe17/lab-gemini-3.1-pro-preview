#!/usr/bin/env python3.12
"""step1 골격 groundtruth 검수용 report.html 생성.

inputs/p-NNN.png + groundtruth/p-NNN.json → self-contained report.html
좌: 페이지 탭 + 렌더 PNG / 우: 골격 카드 + 필드별 승인/거부 + 수정 textarea
"""
import base64
import json
import html
from pathlib import Path

HERE = Path(__file__).parent
INPUTS = HERE / "inputs"
GT = HERE / "groundtruth"
ORDER = ["p-038", "p-005", "p-011", "p-017", "p-007"]  # 난이도순 L1→L4


def b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()


def esc(x) -> str:
    return html.escape(str(x))


def merges_rows(merges: list[dict]) -> str:
    if not merges:
        return '<tr><td colspan="3" class="muted">병합 없음</td></tr>'
    out = []
    for m in merges:
        d = "행" if m.get("direction") == "rows" else "열"
        out.append(f'<tr><td>{esc(m.get("anchor_label",""))}</td>'
                   f'<td>{d}</td><td>{esc(m.get("span_count",""))}</td></tr>')
    return "".join(out)


def spans_rows(spans: list[dict]) -> str:
    if not spans:
        return '<tr><td colspan="2" class="muted">다단 헤더 없음</td></tr>'
    return "".join(
        f'<tr><td>{esc(s.get("parent_label",""))}</td>'
        f'<td>{esc(", ".join(s.get("covers",[])))}</td></tr>' for s in spans)


def uncertain_html(u: list[str]) -> str:
    if not u:
        return ""
    items = "".join(f"<li>{esc(x)}</li>" for x in u)
    return f'<div class="uncertain"><b>⚠️ 불확실 (검수 필요)</b><ul>{items}</ul></div>'


def field_row(key: str, label: str, val) -> str:
    return f'''<tr data-field="{key}">
      <td class="k">{esc(label)}</td>
      <td class="v">{esc(val)}</td>
      <td class="vote">
        <label class="ok"><input type="radio" name="{{pid}}-{key}" value="ok">승인</label>
        <label class="no"><input type="radio" name="{{pid}}-{key}" value="no">거부</label>
      </td>
      <td><input class="fix" type="text" placeholder="수정값/지시"></td>
    </tr>'''


def page_section(pid: str, idx: int) -> str:
    gt = json.loads((GT / f"{pid}.json").read_text())
    meta = gt.get("_meta", {})
    img = b64(INPUTS / f"{pid}.png")
    rows = "".join([
        field_row("total_columns", "total_columns (열 수)", gt.get("total_columns")),
        field_row("header_levels", "header_levels (헤더 단)", gt.get("header_levels")),
        field_row("body_row_count", "body_row_count (본문 행)", gt.get("body_row_count")),
    ]).replace("{pid}", pid)

    spans = spans_rows(gt.get("header_spans", []))
    merges = merges_rows(gt.get("merges", []))
    unc = uncertain_html(gt.get("_uncertain", []))
    active = " active" if idx == 0 else ""
    return f'''
<section class="page{active}" id="sec-{pid}">
  <div class="img-col">
    <img src="data:image/png;base64,{img}" alt="{pid}">
  </div>
  <div class="data-col">
    <div class="badges">
      <span class="lv">{esc(meta.get("level",""))}</span>
      <span class="pid">{esc(pid)}</span>
      <span class="draft">{esc(meta.get("labeled",""))}</span>
    </div>
    <p class="note">{esc(meta.get("note",""))}</p>
    {unc}
    <table class="scalar">
      <thead><tr><th>필드</th><th>초안값</th><th>검수</th><th>수정</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <h4>header_spans</h4>
    <table class="sub"><thead><tr><th>parent_label</th><th>covers</th></tr></thead>
      <tbody>{spans}</tbody></table>
    <h4>merges</h4>
    <table class="sub"><thead><tr><th>anchor_label</th><th>방향</th><th>span</th></tr></thead>
      <tbody>{merges}</tbody></table>
    <div class="page-fb">
      <label>페이지 총평 <textarea rows="2" placeholder="이 페이지 골격 전반 수정 지시"></textarea></label>
    </div>
  </div>
</section>'''


def main() -> None:
    tabs = "".join(
        f'<button class="tab{" active" if i==0 else ""}" data-pid="{p}">'
        f'{p} <em>{json.loads((GT/f"{p}.json").read_text())["_meta"]["level"]}</em></button>'
        for i, p in enumerate(ORDER))
    sections = "".join(page_section(p, i) for i, p in enumerate(ORDER))

    doc = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>step1 골격 GT 검수</title>
<style>
:root{{--bg:#0f1115;--card:#1a1d24;--line:#2c313c;--fg:#e6e8ec;--mut:#8b93a1;--ok:#3cb44b;--no:#e6194B;--warn:#f5a623;}}
*{{box-sizing:border-box}}
body{{margin:0;font:14px/1.5 -apple-system,'Apple SD Gothic Neo',sans-serif;background:var(--bg);color:var(--fg)}}
header.top{{padding:12px 18px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:9}}
header.top h1{{margin:0 0 4px;font-size:16px}}
header.top .stats{{color:var(--mut);font-size:12px}}
.tabs{{display:flex;gap:6px;padding:10px 18px;flex-wrap:wrap;border-bottom:1px solid var(--line);position:sticky;top:52px;background:var(--bg);z-index:8}}
.tab{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}}
.tab em{{color:var(--warn);font-style:normal;font-size:11px;margin-left:4px}}
.tab.active{{border-color:var(--warn);color:#fff}}
.page{{display:none;grid-template-columns:minmax(380px,1fr) minmax(420px,1fr);gap:18px;padding:18px;align-items:start}}
.page.active{{display:grid}}
.img-col{{position:sticky;top:108px}}
.img-col img{{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}}
.data-col h4{{margin:16px 0 6px;color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
.badges{{display:flex;gap:8px;align-items:center;margin-bottom:8px}}
.badges span{{font-size:12px;padding:2px 8px;border-radius:6px;border:1px solid var(--line)}}
.badges .lv{{background:#2a2118;color:var(--warn);border-color:#4a3a1f}}
.badges .draft{{background:#241a24;color:#d98fd9}}
.note{{color:var(--mut);font-size:13px;margin:4px 0 10px}}
.uncertain{{background:#2a2118;border:1px solid #4a3a1f;border-radius:8px;padding:8px 12px;margin-bottom:12px;font-size:13px}}
.uncertain ul{{margin:4px 0 0;padding-left:18px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
th,td{{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{background:#13161c;color:var(--mut);font-size:11px;font-weight:600}}
td.k{{color:var(--mut);width:38%}}
td.v{{font-weight:600;font-variant-numeric:tabular-nums}}
.muted{{color:var(--mut);text-align:center}}
.vote{{white-space:nowrap}}
.vote label{{font-size:12px;margin-right:6px;cursor:pointer}}
.vote .ok{{color:var(--ok)}} .vote .no{{color:var(--no)}}
.fix{{width:100%;background:#0d0f13;border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:4px 6px}}
.page-fb{{margin-top:14px}}
.page-fb textarea{{width:100%;background:#0d0f13;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px;margin-top:4px}}
tr.row-ok{{background:rgba(60,180,75,.10)}} tr.row-no{{background:rgba(230,25,75,.12)}}
.exportbar{{padding:14px 18px;border-top:1px solid var(--line)}}
button.exp{{background:var(--ok);color:#04210a;border:0;border-radius:8px;padding:8px 16px;font-weight:700;cursor:pointer}}
pre#out{{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 18px;display:none}}
</style></head><body>
<header class="top">
  <h1>step1 — 이미지 골격 GT 검수</h1>
  <div class="stats">model: google/gemini-3.1-pro-preview · 이미지 5장 (L1~L4) · groundtruth: <b>draft</b> · 검수 후 ‘report.html 반영해줘’ 요청하면 JSON 갱신</div>
</header>
<div class="tabs">{tabs}</div>
{sections}
<div class="exportbar">
  <button class="exp" onclick="exportFb()">검수 결과 JSON 추출</button>
  <span style="color:var(--mut);font-size:12px;margin-left:10px">추출된 JSON을 복사해 전달하거나, 저장 후 ‘반영해줘’ 요청</span>
</div>
<pre id="out"></pre>
<script>
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  document.getElementById('sec-'+t.dataset.pid).classList.add('active');
}});
document.querySelectorAll('.vote input').forEach(r=>r.onchange=e=>{{
  const tr=e.target.closest('tr');tr.classList.remove('row-ok','row-no');
  tr.classList.add(e.target.value==='ok'?'row-ok':'row-no');
}});
function exportFb(){{
  const res={{}};
  document.querySelectorAll('.page').forEach(sec=>{{
    const pid=sec.id.replace('sec-','');const fields={{}};
    sec.querySelectorAll('tr[data-field]').forEach(tr=>{{
      const f=tr.dataset.field;
      const v=tr.querySelector('input[type=radio]:checked');
      const fix=tr.querySelector('.fix').value.trim();
      if(v||fix) fields[f]={{vote:v?v.value:null,fix:fix||null}};
    }});
    const note=sec.querySelector('.page-fb textarea').value.trim();
    if(Object.keys(fields).length||note) res[pid]={{fields,note:note||null}};
  }});
  const o=document.getElementById('out');
  o.style.display='block';o.textContent=JSON.stringify(res,null,2);
  o.scrollIntoView({{behavior:'smooth'}});
}}
</script></body></html>'''
    out = HERE / "report.html"
    out.write_text(doc, encoding="utf-8")
    print(f"✓ {out}  ({len(doc)//1024} KB)")


if __name__ == "__main__":
    main()
