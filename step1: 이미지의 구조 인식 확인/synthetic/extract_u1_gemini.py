#!/usr/bin/env python3.12
"""U1 (네이티브 Gemini 백엔드) — 표 이미지 → 빈 셀 골격 HTML. **반복-측정 하니스.**

OpenRouter(extract_u1.py) 대신 네이티브 google-genai SDK로 호출한다. media_resolution
(이미지 토큰화 크기)을 제어하려는 것이 목적이며, 그 위에 **측정 노이즈를 정량화**한다.

측정 원칙(중요):
- Gemini 3은 temperature 1.0 권장(docs/prompt.md: temp<1.0은 looping/degradation 경고).
  고엔트로피 입력(예: s6)은 temp 1.0에서 실행마다 출력이 흔들리므로 **단일 실행 점수는 신뢰 불가**.
- 따라서 조건마다 **N회 반복** → 점수 평균±표준편차, 그리고 **최빈 구조(modal)·동의율**을 함께 기록.
- temp=0(그리디)도 -temp로 시도 가능하나 권장 안 함(위 경고). temp=0이면 결정론적이라 N=1로 강제.

축:
- 고정: 프롬프트 v1.1, thinking_level=low
- 스윕: media_resolution ∈ {low, medium, high}   ← per-sample 파일 태그
- 반복: n (기본 5)

사용:
  python3.12 extract_u1_gemini.py s6-p011clone -mr high          # n=5, temp=1.0(기본)
  python3.12 extract_u1_gemini.py s6-p011clone -mr high -n 5
  python3.12 extract_u1_gemini.py -mr high -n 1                  # 전체 7장, 1회(저엔트로피 sanity)
  python3.12 extract_u1_gemini.py s6-p011clone -mr high -temp 0  # 그리디(권장X), n 자동 1
  python3.12 extract_u1_gemini.py --rebuild-log
출력:
  u1/v<N>/<id>.<mr>.json   결과(반복 runs + 집계 + 입력구성)
  u1/v<N>/<id>.<mr>.html   **최빈(modal) 골격**
  u1/v<N>/_config.json · runlog-v<N>.md
"""
import json
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

from skeletonize import skeletonize
from teds import teds_struct_html
from extract_u1 import PROMPTS  # 프롬프트 단일 소스 재사용

HERE = Path(__file__).parent
PNG = HERE / "png"
GT = HERE / "gt"
U1 = HERE / "u1"

VERSION = "2.1"              # 2.1 = 반복-측정(분포). v2(단일 실행)는 '노이즈 baseline'으로 보존.
BACKEND = "gemini"
MODEL = "gemini-3.1-pro-preview"
PROMPT_KEY = "1.1"
THINKING_LEVEL = "low"
MAX_OUTPUT_TOKENS = 16000

# 측정 노브 (main에서 CLI로 덮어씀). Gemini 3 권장 temp=1.0.
TEMPERATURE = 1.0
N = 5

SYSTEM = PROMPTS[PROMPT_KEY]["system"]
TASK = PROMPTS[PROMPT_KEY]["task"]
FEWSHOT = PROMPTS[PROMPT_KEY]["fewshot"]

MRES = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
}
_TL = {"low": types.ThinkingLevel.LOW, "medium": types.ThinkingLevel.MEDIUM, "high": types.ThinkingLevel.HIGH}

_TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
_HARD = ("PERMISSION_DENIED", "403", "401", "400")


def prompt_config() -> dict:
    return {
        "version": VERSION,
        "backend": BACKEND,
        "model": MODEL,
        "prompt_from": PROMPT_KEY,
        "params": {"temperature": TEMPERATURE, "n": N,
                   "thinking_level": THINKING_LEVEL, "max_output_tokens": MAX_OUTPUT_TOKENS},
        "sweep_axis": "media_resolution",
        "measurement": (f"n={N}회 반복 · temperature={TEMPERATURE} · "
                        f"점수=평균±표준편차 · 구조=최빈(modal)·동의율"),
        "system": SYSTEM,
        "task": TASK,
        "fewshot": FEWSHOT,
    }


def vdir() -> Path:
    d = U1 / f"v{VERSION}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_key() -> str:
    import os
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    envf = HERE.parents[1] / ".env" / ".env"
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line.startswith("GEMINI_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("GEMINI_API_KEY 못 찾음 (.env/.env 확인)")


_CLIENT = None


def client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = genai.Client(api_key=load_key())
    return _CLIENT


def clean_html(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:html)?\s*|\s*```$", "", t, flags=re.S)
    m = re.search(r"<table.*</table>", t, re.S | re.I)
    return m.group(0) if m else t


def _call_once(png_bytes: bytes, mr: str):
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        media_resolution=MRES[mr],
        thinking_config=types.ThinkingConfig(thinking_level=_TL[THINKING_LEVEL]),
    )
    contents = [types.Content(role="user", parts=[
        types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
        types.Part.from_text(text=TASK),
    ])]
    return client().models.generate_content(model=MODEL, contents=contents, config=cfg)


def call_retry(png_bytes: bytes, mr: str):
    """일시 오류(503/429)만 백오프 재시도. 하드 오류(403 등)는 즉시 중단."""
    for attempt in range(4):
        try:
            return _call_once(png_bytes, mr)
        except Exception as e:
            msg = str(e).replace("\n", " ")
            if any(h in msg for h in _HARD):
                sys.exit(f"하드 오류(접근 거부 등) — 계정/프로젝트 확인 필요. 중단.\n{msg[:200]}")
            if attempt < 3 and any(t in msg for t in _TRANSIENT):
                print(f"  · 일시 오류, 백오프 재시도({attempt + 1})…", flush=True)
                time.sleep(15 * (attempt + 1))
            else:
                raise


def _ttok(u):
    return getattr(u, "total_token_count", None)


def _rtok(u):
    return getattr(u, "thoughts_token_count", None) or 0


# ── 반복 측정 ─────────────────────────────────────────────────────────────────

def run_condition(page: str, mr: str) -> None:
    png_bytes = (PNG / f"{page}.png").read_bytes()
    gt_skel = (GT / f"{page}.skeleton.html").read_text(encoding="utf-8")
    runs = []
    for i in range(N):
        res = call_retry(png_bytes, mr)
        raw = res.text or ""
        skel = skeletonize(clean_html(raw))
        score = teds_struct_html(skel, gt_skel)
        u = res.usage_metadata
        runs.append({
            "i": i, "teds": score, "pred_skeleton": skel, "raw": raw,
            "total_tokens": _ttok(u), "reasoning_tokens": _rtok(u),
            "cost": None,  # 네이티브는 $ 미보고
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        })

    scores = [r["teds"] for r in runs]
    skels = Counter(r["pred_skeleton"] for r in runs)
    modal_skel, modal_count = skels.most_common(1)[0]
    modal_teds = next(r["teds"] for r in runs if r["pred_skeleton"] == modal_skel)
    mean = statistics.mean(scores)
    std = statistics.pstdev(scores) if len(scores) > 1 else 0.0

    def _mean_int(key):
        vals = [r[key] for r in runs if isinstance(r[key], (int, float))]
        return round(statistics.mean(vals)) if vals else None

    d = vdir()
    (d / f"{page}.{mr}.html").write_text(modal_skel + "\n", encoding="utf-8")  # 최빈 구조
    rec = {
        "page": page, "level": mr, "version": VERSION,
        "backend": BACKEND, "model": MODEL, "media_resolution": mr,
        "thinking_level": THINKING_LEVEL, "temperature": TEMPERATURE, "n": N,
        "teds_struct": mean,           # 레거시 리더 호환(=평균)
        "teds_mean": mean, "teds_std": std, "teds_min": min(scores), "teds_max": max(scores),
        "teds_scores": scores,
        "modal_teds": modal_teds, "modal_count": modal_count, "agreement": modal_count / N,
        "distinct_structures": len(skels),
        "usage_mean": {"total_tokens": _mean_int("total_tokens"),
                       "reasoning_tokens": _mean_int("reasoning_tokens"), "cost": None},
        "system": SYSTEM, "task": TASK, "fewshot_n": len(FEWSHOT),
        "modal_skeleton": modal_skel,
        "runs": runs,
    }
    (d / f"{page}.{mr}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    write_config()
    rebuild_log()
    print(f"{page:16} mr={mr:6} TEDS={mean:.3f}±{std:.3f} "
          f"(n={N}, agree={modal_count}/{N}, structs={len(skels)}, range={min(scores):.3f}~{max(scores):.3f})",
          flush=True)


# ── 산출물 기록 ───────────────────────────────────────────────────────────────

def write_config() -> None:
    (vdir() / "_config.json").write_text(
        json.dumps(prompt_config(), ensure_ascii=False, indent=2), encoding="utf-8")


def _records() -> list:
    recs = []
    for f in vdir().glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            recs.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    recs.sort(key=lambda r: (r.get("page", ""), {"low": 0, "medium": 1, "high": 2}.get(r.get("level"), 9)))
    return recs


def _log_entry(rec: dict) -> str:
    n = rec.get("n", 1)
    return (
        f"### {rec.get('page','?')} · media_resolution={rec.get('level','?')}\n\n"
        f"- 시각: {rec.get('runs',[{}])[0].get('timestamp','(기록 없음)') if rec.get('runs') else '(기록 없음)'}\n"
        f"- 입력: `png/{rec.get('page','?')}.png` · thinking_level={rec.get('thinking_level','?')} · "
        f"temperature={rec.get('temperature','?')} · n={n}\n"
        f"- TEDS: **{rec.get('teds_mean', float('nan')):.3f} ± {rec.get('teds_std', 0):.3f}** "
        f"(range {rec.get('teds_min', float('nan')):.3f}~{rec.get('teds_max', float('nan')):.3f}, "
        f"scores={['%.3f' % s for s in rec.get('teds_scores', [])]})\n"
        f"- 구조 동의율: {rec.get('modal_count','?')}/{n} (서로 다른 구조 {rec.get('distinct_structures','?')}종) · "
        f"modal TEDS {rec.get('modal_teds', float('nan')):.3f}\n"
        f"- 토큰(평균): total {rec.get('usage_mean',{}).get('total_tokens','?')} · 비용: 네이티브 $미보고\n\n"
        f"<details><summary>최빈(modal) 골격 HTML</summary>\n\n```html\n{rec.get('modal_skeleton','')}\n```\n</details>\n"
    )


def rebuild_log() -> None:
    cfg = prompt_config()
    header = (
        f"# U1 실행 로그 — v{VERSION} (네이티브 Gemini · 반복 측정)\n\n"
        f"backend `{cfg['backend']}` · model `{cfg['model']}` · 프롬프트 v{cfg['prompt_from']} · "
        f"thinking_level `{THINKING_LEVEL}` · **스윕=media_resolution**.\n\n"
        f"**측정: {cfg['measurement']}.** (temp 1.0 권장 — docs/prompt.md; 고엔트로피 입력은 단일 실행 신뢰 불가 → 반복.)\n\n"
        f"## LLM 입력 구성\n\n"
        f"<details open><summary>① system</summary>\n\n```\n{cfg['system']}\n```\n</details>\n\n"
        f"<details><summary>② few-shot ({len(cfg['fewshot'])} shot)</summary>\n\n(없음 — zero-shot)\n</details>\n\n"
        f"<details><summary>③ task</summary>\n\n```\n{cfg['task']}\n```\n</details>\n\n"
        f"---\n\n## 호출 기록 (조건별 분포)\n\n"
    )
    body = "\n".join(_log_entry(r) for r in _records()) or "_아직 결과 없음._\n"
    (vdir() / "runlog.md").write_text(header + body, encoding="utf-8")


def main() -> None:
    global TEMPERATURE, N
    if "--rebuild-log" in sys.argv:
        write_config()
        rebuild_log()
        print(f"✓ u1/v{VERSION}/_config.json · u1/v{VERSION}/runlog.md  ({len(_records())}건)")
        return
    mr = "high"
    pos = []
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-mr":
            mr = argv[i + 1]; i += 2; continue
        if a == "-temp":
            TEMPERATURE = float(argv[i + 1]); i += 2; continue
        if a == "-n":
            N = int(argv[i + 1]); i += 2; continue
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    if mr not in MRES:
        sys.exit(f"-mr 은 {list(MRES)} 중 하나 (받음: {mr})")
    if TEMPERATURE == 0 and N != 1:
        print(f"⚠ temperature=0(그리디·결정론적) → n={N}→1 강제. (Gemini 3은 temp=1.0 권장)", flush=True)
        N = 1
    pages = [pos[0]] if pos else [p.stem for p in sorted(PNG.glob("*.png"))]
    for page in pages:
        run_condition(page, mr)


if __name__ == "__main__":
    main()
