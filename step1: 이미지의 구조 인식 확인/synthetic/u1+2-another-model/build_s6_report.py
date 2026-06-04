#!/usr/bin/env python3.12
"""s6 구조 비교 리포트 (v2.1 report.html 형식) — Gemini · 전용 파서 · Claude.

각 모델 폴더의 flash 스키마 JSON(modal_skeleton)을 시각 그리드로 렌더(테두리·중첩색).
존재하는 결과만 섹션별로 표시. build_compare 렌더 재사용. TEDS는 중첩 GT 기준(평탄 파서 과소평가).
생성: python3 build_s6_report.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from build_compare import CSS, badge, card, skel_block, img_data_uri, esc  # noqa: E402

PAGE = "s6-p011clone"
GT = (SYN / "gt" / f"{PAGE}.skeleton.html").read_text(encoding="utf-8")
PNGF = SYN / "png" / f"{PAGE}.png"

# (라벨, json 경로, 꼬리표). 존재하는 것만 렌더.
SECTIONS = [
    ("Gemini (thinking=low)", [
        ("gemini-3.1-pro", SYN / "u1" / "v2.1" / f"{PAGE}.high.json", "high"),
        ("gemini-3-flash", HERE / "flash" / f"u1_{PAGE}.high.json", "high"),
        ("gemini-3.5-flash", HERE / "flash35" / f"u1_{PAGE}.high.json", "high"),
    ]),
    ("전용 파서 (평탄 인코딩 — 중첩 GT 기준 과소평가)", [
        ("PaddleOCR-VL-1.6", HERE / "paddle" / f"u1_{PAGE}.json", "flat"),
        ("MinerU2.5-Pro", HERE / "mineru" / f"u1_{PAGE}.json", "flat"),
        ("Nanonets-OCR2-3B", HERE / "nanonets" / f"u1_{PAGE}.json", "flat"),
    ]),
    ("Claude (확장사고 끔)", [
        ("claude-sonnet-4.6", HERE / "sonnet-4.6" / f"u1_{PAGE}.json", ""),
        ("claude-opus-4.6", HERE / "opus-4.6" / f"u1_{PAGE}.json", ""),
        ("claude-opus-4.8", HERE / "opus-4.8" / f"u1_{PAGE}.json", ""),
    ]),
    ("Claude (확장사고 ON · 사고예산/프롬프트 변형)", [
        ("claude-sonnet-4.6", HERE / "sonnet-4.6-think" / f"u1_{PAGE}.json", "+think6k"),
        ("claude-opus-4.8", HERE / "opus-4.8-think" / f"u1_{PAGE}.json", "+think6k ★최고"),
        ("claude-opus-4.8", HERE / "opus-4.8-think12k" / f"u1_{PAGE}.json", "+think12k"),
        ("claude-opus-4.8", HERE / "opus-4.8-think-cprompt" / f"u1_{PAGE}.json", "+think6k+cprompt"),
    ]),
]


def load(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    n = d.get("n", 1)
    return (d.get("modal_skeleton"), d.get("teds_mean"), d.get("teds_std", 0.0),
            n, round(d.get("agreement", 1.0) * n))


def cap(name, tail, mean, std, n, mc):
    t = f" <span class='mut'>{esc(tail)}</span>" if tail else ""
    note = f' <span class="mut">±{std:.3f}·{mc}/{n}</span>' if n > 1 else ""
    return f'<span class="badge b-info">{esc(name)}</span>{t}{badge(mean)}{note}'


def _tval(p):
    p = Path(p)
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    for k in ("teds_mean", "teds_struct"):
        if d.get(k) is not None:
            return d[k]
    return None


def hybrid_section():
    """파서 출력을 LLM 입력으로 넣은 3종 비교(역효과) 표."""
    rows = [
        ("이미지 only", _tval(SYN / "u1" / "v2.1" / f"{PAGE}.high.json"),
         _tval(HERE / "opus-4.8-think" / f"u1_{PAGE}.json")),
        ("MinerU 텍스트 only", _tval(HERE / "mineru-relay" / "gemini-3.1-pro.json"),
         _tval(HERE / "mineru-relay" / "opus-4.8.json")),
        ("이미지 + MinerU 참고", _tval(HERE / "img-plus-mineru" / "gemini-3.1-pro.json"),
         _tval(HERE / "img-plus-mineru" / "opus-4.8.json")),
    ]
    body = []
    for i, (label, g, o) in enumerate(rows):
        cls = "win" if i == 0 else ""
        gc = f'<span class="{cls}">{g:.3f}</span>' if isinstance(g, (int, float)) else "—"
        oc = f'<span class="{cls}">{o:.3f}</span>' if isinstance(o, (int, float)) else "—"
        body.append(f'<tr><td class="l">{esc(label)}</td><td>{gc}</td><td>{oc}</td></tr>')
    return (
        '<div class="cost"><h2>하이브리드 입력 시험 — 파서 출력을 LLM에 넣기 (역효과)</h2>'
        '<p class="legend" style="margin:0 0 8px">같은 s6 구조 과제에서 <b>입력 방식만</b> 바꿈. '
        'MinerU(전용 파서) HTML을 LLM 프롬프트에 넣으면 — 텍스트만이든 이미지와 함께든 — '
        '모델이 파서의 <b>평탄·오류 구조에 정박</b>해 이미지-only보다 떨어진다.</p>'
        '<table class="sum"><thead><tr><th class="l">입력 방식</th>'
        '<th>gemini-3.1-pro</th><th>opus-4.8 +think6k</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
        '<p class="legend" style="margin:8px 0 0">→ <b>이미지-only가 최고</b>(0.85~0.86). 파서 텍스트는 강한 앵커라 '
        'LLM이 베껴 자기 강점을 버림(opus가 더 순응적: 0.44). gemini는 이미지로 중첩 유지+산문-행 제외했으나 그래도 하락(0.78). '
        '<b>올바른 하이브리드 = LLM(이미지, 위상·내용) + 결정론적 선검출(격자)을 피처 단계에서 병합</b> — 파서 완성구조를 프롬프트에 떠넘기지 말 것.</p>'
        '</div>'
    )


def main():
    ref = (card('<span class="badge b-info">입력 PNG (s6)</span>', f'<img src="{img_data_uri(PNGF)}"/>')
           + card('<span class="badge b-gt">정답 골격 · 중첩(nested)</span>', skel_block(GT)))
    blocks = [f'<div class="sample"><h2>입력 + 정답</h2><div class="cards">{ref}</div></div>']
    for title, entries in SECTIONS:
        cards = []
        for name, p, tail in entries:
            if not Path(p).exists():
                continue
            skel, mean, std, n, mc = load(p)
            if skel is None:
                continue
            cards.append(card(cap(name, tail, mean, std, n, mc), skel_block(skel)))
        if cards:
            blocks.append(f'<div class="sample"><h2>{esc(title)}</h2><div class="cards">{"".join(cards)}</div></div>')

    note = (
        '<div class="cost"><h2>읽는 법</h2>'
        '<p class="legend" style="margin:0 0 8px">테두리: 검정=외곽 · <b>빨강=1단계 중첩표</b> · <i>보라=2단계</i>. '
        'TEDS=<b>중첩 정답 기준</b> 평균±σ(n>1). 평탄 파서는 인코딩 차이로 과소평가됨.</p>'
        '<ul style="font-size:13px;line-height:1.6;margin:0;padding-left:18px">'
        '<li><b>Gemini</b>: 중첩 컨벤션 따름 → TEDS 높음(0.85~0.875). 단 중첩표 윗줄 빈칸을 colspan=2로 병합(지각 미스).</li>'
        '<li><b>전용 파서</b>: 평탄 9열. PaddleOCR이 가장 깔끔(빈칸 분리), MinerU는 산문을 표행으로 흡수해 더 낮음.</li>'
        '<li><b>Claude</b>: s6에서 grid 불규칙(rowspan/colspan 엉킴, 산문 흡수). 확장사고 ON/OFF 비교가 공정성 관건.</li>'
        '</ul></div>'
    )

    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>s6 구조 비교 — Gemini · 전용파서 · Claude</title><style>{CSS}</style></head><body>
<h1>s6 구조 골격 비교 (시각)</h1>
<p class="sub">입력 1장(s6, 실문서 중첩 난표) · 모델별 골격을 시각 그리드로 · <a href="index.html">← 수치 인덱스</a></p>
{note}
{"".join(blocks)}
{hybrid_section()}
</body></html>"""
    (HERE / "report.html").write_text(doc, encoding="utf-8")
    n_cards = doc.count('class="card"')
    print(f"✓ report.html  (카드 {n_cards}개)")


if __name__ == "__main__":
    main()
