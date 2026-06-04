#!/usr/bin/env python3.12
"""synthetic/index.html — 절차(u1→u2)·버전 중심 인덱스.

각 버전 폴더(u1/v*/, u2/)에 데이터·리포트·로그가 함께 있고, 이 인덱스가 그리로 링크한다.
u1/v*/_config.json 을 스캔해 '무엇을 바꿨나' 한 줄 설명을 만든다.
사용: python3 build_index.py
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
U1 = HERE / "u1"
U2 = HERE / "u2"


def esc(x) -> str:
    return html.escape(str(x))


def vkey(v: str):
    return tuple(int(p) for p in re.findall(r"\d+", v)) or (0,)


def u1_entries():
    out = []
    for d in sorted(U1.glob("v*"), key=lambda p: vkey(p.name[1:])):
        cfg_f = d / "_config.json"
        if not cfg_f.exists():
            continue
        cfg = json.loads(cfg_f.read_text(encoding="utf-8"))
        v = cfg.get("version", d.name[1:])
        backend = cfg.get("backend", "openrouter")
        prompt = cfg.get("prompt_from", v)
        sweep = cfg.get("sweep_axis", "thinking")
        meas = cfg.get("measurement", "단일 실행 (n=1)")
        params = cfg.get("params", {})
        out.append({
            "v": v,
            "report": f"u1/{d.name}/report.html" if (d / "report.html").exists() else None,
            "log": f"u1/{d.name}/log.html" if (d / "log.html").exists() else None,
            "desc": f"backend <b>{esc(backend)}</b> · 프롬프트 v{esc(prompt)} · 스윕 <b>{esc(sweep)}</b> · {esc(meas)}",
            "params": " · ".join(f"{esc(k)}={esc(val)}" for k, val in params.items()),
        })
    return out


def u2_entry():
    vf = U2 / "_verdict.md"
    if not (U2 / "report.html").exists() and not vf.exists():
        return None
    line = ""
    if vf.exists():
        m = re.search(r"## 자동 판정\s*\n+\*\*(.+?)\*\*", vf.read_text(encoding="utf-8"))
        if m:
            line = m.group(1)
    return {
        "report": "u2/report.html" if (U2 / "report.html").exists() else None,
        "verdict": "u2/verdict.html" if (U2 / "verdict.html").exists() else None,
        "line": line,
    }


CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:28px;background:#f5f5f7;color:#111;max-width:980px;}
h1{font-size:22px;margin:0 0 4px;} .sub{color:#666;font-size:13px;margin:0 0 22px;}
h2{font-size:16px;margin:26px 0 4px;padding-bottom:6px;border-bottom:2px solid #d8d9de;}
h2 .tag{font-size:12px;color:#888;font-weight:400;margin-left:8px;}
.row{display:flex;align-items:baseline;gap:12px;padding:11px 14px;background:#fff;border:1px solid #e2e2e6;border-radius:9px;margin:8px 0;}
.row .name{font-weight:700;font-size:14px;min-width:74px;}
.row .desc{flex:1;color:#333;font-size:13px;}
.row .desc .p{display:block;color:#999;font-size:11.5px;margin-top:2px;}
.row a{font-size:13px;text-decoration:none;color:#1769d6;white-space:nowrap;}
.row a.dim{color:#999;} .row .gone{color:#bbb;font-size:12px;}
.verdict{background:#fff5e6;border:1px solid #f0c97a;border-radius:8px;padding:8px 12px;color:#7a4a00;font-size:12.5px;margin-top:6px;}
.path{color:#aaa;font-size:11px;margin-left:6px;}
"""


def main() -> None:
    u1 = u1_entries()
    u2 = u2_entry()

    u1_rows = []
    for e in u1:
        link = (f'<a href="{e["report"]}">리포트 ▸</a>' if e["report"]
                else '<span class="gone">리포트 없음</span>')
        log = f'<a class="dim" href="{e["log"]}">log</a>' if e["log"] else ''
        u1_rows.append(
            f'<div class="row"><span class="name">v{esc(e["v"])}</span>'
            f'<span class="desc">{e["desc"]}<span class="p">{e["params"]}'
            f'<span class="path">📁 u1/v{esc(e["v"])}/</span></span></span>{link} {log}</div>')

    u2_html = ""
    if u2:
        link = (f'<a href="{u2["report"]}">리포트 ▸</a>' if u2["report"]
                else '<span class="gone">리포트 없음</span>')
        vlink = f'<a class="dim" href="{u2["verdict"]}">verdict</a>' if u2["verdict"] else ''
        vline = f'<div class="verdict">판정: {esc(u2["line"])}</div>' if u2["line"] else ""
        u2_html = (
            '<h2>u2 — 해리 검사 <span class="tag">지각 vs 생산 (HTML 우회, 개수 질문)</span></h2>'
            f'<div class="row"><span class="name">u2</span>'
            f'<span class="desc">위치/개수 질문으로 직렬화를 빼고 <b>지각 단독</b> 측정 · 대조+삼각측량 · n=5'
            f'<span class="path">📁 u2/</span>{vline}</span>{link} {vlink}</div>')

    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>합성 표 구조 인식 — 인덱스</title><style>{CSS}</style></head><body>
<h1>합성 표 구조 인식 실험 — 인덱스</h1>
<p class="sub">절차·버전 폴더 중심. 각 폴더(u1/v*/, u2/)에 데이터·리포트·로그가 함께 있음.
각 행: 무엇을 바꿨나 · 폴더 · 리포트(HTML, 자체완결) · log. TEDS=구조 트리편집 유사도(1=완벽).</p>
<h2>u1 — 구조 골격 추출 <span class="tag">표 이미지 → 빈 셀 HTML 골격, TEDS-Struct</span></h2>
{"".join(u1_rows) if u1_rows else '<p class="gone">결과 없음</p>'}
{u2_html}
</body></html>"""
    (HERE / "index.html").write_text(doc, encoding="utf-8")
    print(f"✓ index.html  (u1 {len(u1)}개" + (" + u2" if u2 else "") + ")")


if __name__ == "__main__":
    main()
