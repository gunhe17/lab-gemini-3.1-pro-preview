#!/usr/bin/env python3
"""step1 최종 종합 리포트 생성 → step1/report.html (자체완결).
모델 특성 → 시도 → 결과 → 마무리 서술. 중심 이미지(s6) 임베드 + 하위 리포트 링크.
사용: python3 build_final_report.py
"""
import base64
from pathlib import Path

HERE = Path(__file__).parent           # step1 폴더
SYN = HERE / "synthetic"
s6 = "data:image/png;base64," + base64.b64encode((SYN / "png" / "s6-p011clone.png").read_bytes()).decode()

CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:32px;background:#f5f5f7;color:#1a1d24;max-width:1000px;line-height:1.7;}
h1{font-size:23px;margin:0 0 6px;} h2{font-size:18px;margin:30px 0 6px;border-bottom:2px solid #d8d9de;padding-bottom:6px;}
h3{font-size:15px;margin:18px 0 4px;color:#0a4;}
.lead{background:#0f1115;color:#e6e8ec;border-radius:10px;padding:16px 20px;margin:8px 0 20px;}
.lead b{color:#7cff9b;}
.step{background:#fff;border:1px solid #e2e2e6;border-radius:10px;padding:14px 20px;margin:12px 0;}
.why{color:#7a4a00;background:#fff5e6;border-left:4px solid #f0c97a;padding:6px 12px;margin:6px 0;border-radius:4px;font-size:14px;}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:8px 0;background:#fff;}
th,td{border:1px solid #e0e0e0;padding:6px 10px;text-align:center;} th{background:#f0f1f4;} td.l,th.l{text-align:left;}
.win{color:#2a8f2a;font-weight:700;} .bad{color:#c0392b;font-weight:700;} .mut{color:#888;}
.cur{background:#fbf3f3;}
img.s6{max-width:420px;border:1px solid #ccc;border-radius:8px;float:right;margin:0 0 10px 16px;}
ul{margin:6px 0;} a{color:#1769d6;} .files a{display:inline-block;margin:2px 10px 2px 0;}
.k{font-weight:700;}
"""

HTML = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>step1 — 이미지의 구조 인식 확인 · 최종 결과</title><style>{CSS}</style></head><body>

<h1>step1 — 이미지의 구조 인식 확인 · 최종 종합</h1>
<p class="mut">복잡 표 이미지 → MD/HTML 파이프라인에서, 이 비전 모델이 "구조"를 어디까지 인식하는지 / 어디서 무너지는지 / 무엇으로 메우는지를 단계적으로 규명한 기록.</p>

<div class="lead">
<b>한 줄 결론.</b> 프런티어 VLM(Gemini·Claude)은 <b>표의 텍스트·내용 전사는 사실상 완벽</b>하지만,
<b>가느다란 빈 칸이 만드는 미세 격자 구조</b>에서 공통적으로 무너진다(빈 칸을 옆 칸과 병합). 이 한계는
프롬프트·사고예산·모델 교체로 안정적으로 뚫리지 않는 <b>지각 단계의 천장</b>이다. 따라서 운영 해법은
"더 좋은 모델 찾기"가 아니라 <b>VLM(내용) + 결정론적 선검출(격자) 하이브리드</b>다.
</div>

<img class="s6" src="{s6}" alt="s6"/>

<h2>0. 출발점 — 모델의 특성(가설1)</h2>
<div class="step">
<div class="why">모델 특성: 좌표·계량 출력은 <b>0–1000으로 양자화된 토큰 예측</b>이라 구조적으로 약하고, 텍스트·관계 신호는 상대적 강점이다(docs/가설1.md).</div>
그래서 좌표를 빼고 <b>관계·구조(골격)만</b> 격리해 측정하기로 했다. 우측 이미지가 이 전체 실험의 중심 난표 <b>s6</b>:
'기존/변경' 칸 안에 작은 표가 중첩되고, 머리글 좌측 칸들이 <b>비어</b> 있는 한국어 실문서 구조다.
</div>

<h2>1. 골격 격리 — 실제 이미지</h2>
<div class="step">
<div class="why">"좌표가 약하면 구조는 강할까?" → 빈 셀 골격만 추출시켜 측정.</div>
실문서 5장에서 <span class="k">위상(헤더 정체성·중첩 존재·셀 타입)은 L4까지 생존</span>했지만,
<span class="k">계수/정규화(모든 행이 같은 열 수로 해소)는 난이도 따라 단조 붕괴</span>(열-정규화 일관성 0.86→0.25).
난이도≠단조였고, 진짜 변수는 <b>무괘선·세로병합·빈칸 밀도</b>였다.
</div>

<h2>2. 합성 사다리 — 변수 통제</h2>
<div class="step">
<div class="why">실문서는 변수가 섞여 있어 원인 분리가 안 됨 → 직접 쓴 HTML(=완벽한 정답)로 난점을 한 칸씩 누적.</div>
s0~s5(깨끗한 합성)는 <b>최소 사고로 전부 1.000</b>. 오직 <b>실문서를 충실히 복제한 s6만 붕괴</b>.
<b>"깨끗한 합성표는 모델을 과대평가한다"</b> — 벤치엔 실문서 복제본이 반드시 필요하다는 교훈.
저해상 실패 양상 = <b>중첩 평탄화</b>(2D→1D 표류).
</div>

<h2>3. u1 — 구조 골격, 그리고 측정의 함정</h2>
<div class="step">
<div class="why">프롬프트·해상도·사고를 바꿔 s6 구조 점수를 올릴 수 있나?</div>
<ul>
<li><b>프롬프트(v1.1, docs/prompt.md식 XML)</b>: 평문 규칙(v1)보다 안정·향상.</li>
<li><b>media_resolution 스윕(native, n=5)</b>: low 0.458 → medium 0.735 → high 0.850. 해상도는 평균↑·분산↓(엔트로피를 낮춤)지만 <b>0.875 천장은 못 뚫음</b>.</li>
<li><b>결정적 발견</b>: temperature=1.0 단일 실행은 <b>측정 노이즈</b>. s6는 고엔트로피라 호출마다 출렁였다 → <b>n=5 반복(평균±σ·최빈)</b>으로 측정 자체를 고정. (Gemini 3은 temp 1.0 권장이라 temp=0 대신 반복으로.)</li>
</ul>
</div>

<h2>4. u2 — 해리 검사: 지각이냐 생산이냐</h2>
<div class="step">
<div class="why">s6의 잔여 오차(빈칸을 colspan=2로 병합)가 "못 본 것(지각)"인지 "봤는데 받아쓰다 망친 것(생산)"인지 분리.</div>
HTML을 우회하고 <b>"그 줄 칸이 몇 개냐"</b>만 물었다(대조+삼각측량, n=5).
대조(바깥 머리글=5)는 5/5 정답 → 측정 유효. 그런데 타깃(중첩표 윗줄, 정답 3)을 <b>5/5로 '2'</b>로 답함.
즉 <b>모델은 빈 칸을 지각 단계에서 일관되게 병합</b>한다 — 생산 실패가 아니라 <b>지각 실패</b>. 해상도로도 안 바뀜.
</div>

<h2>5. 모델 비교 — "더 좋은 모델이 뚫나?"</h2>
<div class="step">
<div class="why">전용 파서·다른 프런티어 모델로 교체하면 s6 천장이 뚫리나? (OmniDocBench TEDS-S 근거: 3.1-pro 85.4 &lt; 3-flash 92.6, dedicated 95~96)</div>
<table>
<thead><tr><th class="l">모델 (s6, 동일 조건)</th><th>구조 TEDS</th><th>인코딩 / 비고</th></tr></thead>
<tbody>
<tr><td class="l">gemini-3-flash</td><td class="win">0.875</td><td class="l">중첩 · 안정(5/5) · Gemini 최상위</td></tr>
<tr><td class="l">claude-opus-4.8 <span class="mut">+확장사고</span></td><td>0.864</td><td class="l">중첩 · ≈Gemini 동률(사고 필수)</td></tr>
<tr class="cur"><td class="l">gemini-3.1-pro (출발 모델)</td><td>0.850</td><td class="l">중첩 · 빈칸 병합</td></tr>
<tr><td class="l">gemini-3.5-flash</td><td>0.815</td><td class="l">불안정</td></tr>
<tr><td class="l">PaddleOCR-VL-1.6 (전용)</td><td>0.531</td><td class="l">평탄 인코딩 — 중첩 GT 기준 과소평가, <b>빈칸은 분리</b></td></tr>
<tr><td class="l">MinerU2.5-Pro (전용)</td><td>0.406</td><td class="l">평탄 + 산문을 표행으로 흡수</td></tr>
<tr><td class="l">claude-opus-4.8 <span class="mut">사고 끔</span></td><td class="bad">0.388</td><td class="l">불규칙 (사고 없으면 무너짐)</td></tr>
</tbody></table>
<b>발견:</b> (1) <b>아무 모델도 0.875를 안정적으로 못 뚫음.</b> (2) Claude는 <b>확장사고를 줘야</b> Gemini급(0.388→0.864) — 단 사고예산↑(12k)·정교 프롬프트(+cprompt)는 오히려 퇴화(0.53·0.62). (3) 전용 파서는 <b>평탄 인코딩</b>이라 중첩 GT 기준 점수는 낮지만 빈칸은 분리(컨벤션 차이). (4) u2 재확인: <b>Gemini도 Claude도 직접 물으면 빈칸을 '2'로 병합</b> — 프런티어 VLM 공통 지각 한계.
</div>

<h2>6. u3 — 강점으로 전환: 완전 콘텐츠 변환</h2>
<div class="step">
<div class="why">가설1대로 "텍스트·관계는 강점"이라면, 골격이 아니라 <b>내용까지(HTML+MD)</b> 변환시키면 강점이 드러날 것.</div>
<table>
<thead><tr><th class="l">모델 (s6 → HTML+MD)</th><th>콘텐츠 유사도</th><th>구조 TEDS</th></tr></thead>
<tbody>
<tr><td class="l">gemini-3-flash (gemini-튜닝 프롬프트)</td><td class="win">1.000</td><td>0.781</td></tr>
<tr><td class="l">claude-opus-4.8 (claude-튜닝 +사고)</td><td class="bad">0.666</td><td>0.531</td></tr>
</tbody></table>
<b>gemini-3-flash는 모든 텍스트(불릿·㉔㉕ 기호까지)를 한 글자도 안 틀리고 전사</b>(콘텐츠 1.000) — 가설1 입증.
모델의 약점은 늘 <b>격자/좌표</b>였지 <b>내용</b>이 아니었다. 구조만 0.781(그 빈칸-병합 잔여).
</div>

<h2>7. 최종 결론 · 실무 권고</h2>
<div class="step">
<ul>
<li><b>강점/약점이 분리됨:</b> 텍스트·내용 = 거의 완벽(1.0) / 미세 격자(빈 칸 분리) = 공통 천장. 후자는 <b>프롬프트·사고·모델 교체로 안 뚫림</b>(지각 단계 한계).</li>
<li><b>모델 선택:</b> 이 과제엔 <b>gemini-3-flash</b>가 최선 — 구조 최상(0.875)·콘텐츠 완벽(1.0)·저비용·안정. Claude는 <b>확장사고를 켜야</b> 동급(opus-4.8). 출발 모델 gemini-3.1-pro는 동급 대비 약함(85.4).</li>
<li><b>측정 원칙:</b> 고엔트로피 입력은 <b>반드시 n회 반복</b>(단일 temp=1.0 실행은 노이즈). 벤치엔 <b>실문서 복제본</b> 포함 필수.</li>
<li><b>운영 아키텍처(권고):</b> VLM으로 <b>내용 전사 + 위상 인식</b>을 맡기고, <b>빈 칸이 만드는 미세 격자선은 결정론적 선검출(pdfplumber/CV)로 보강</b>하는 <b>하이브리드</b>. 그 격자선은 VLM이 못 보지만 코드가 정확히 잡는, u2가 증명한 바로 그 지점이다.</li>
</ul>
</div>

<h2>산출물 · 드릴다운</h2>
<div class="step files">
<div><span class="k">시각 리포트</span> —
<a href="synthetic/u1+2-another-model/report.html">모델 골격 비교(s6)</a>
<a href="synthetic/u1+2-another-model/index.html">수치·레이아웃 인덱스</a>
<a href="synthetic/u3/report.html">u3 콘텐츠 변환(HTML/MD)</a>
<a href="synthetic/u2/report.html">u2 지각 해리</a></div>
<div><span class="k">단계 데이터</span> — synthetic/u1/ · u2/ · u3/ · u1+2-another-model/(모델별 폴더)</div>
<div><span class="k">실행 코드</span> — synthetic/extract_u1.py · extract_u2.py · extract_u3.py · (멀티모델) u1+2-another-model/run_*.py</div>
<div><span class="k">근거 문서</span> — <a href="docs/가설1.md">docs/가설1.md</a> · <a href="docs/prompt.md">prompt.md</a> · <a href="docs/claude-prompting.md">claude-prompting.md</a> · <a href="docs/paddle.md">paddle.md</a></div>
</div>

</body></html>"""

(HERE / "report.html").write_text(HTML, encoding="utf-8")
print(f"✓ step1/report.html  ({len(HTML)//1024} KB)")
