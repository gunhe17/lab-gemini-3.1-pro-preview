#!/usr/bin/env python3.12
"""U1 — 구조 골격 추출: 표 이미지 → 빈 셀 골격 HTML. (입력 구성 버전 관리 + 실행 로그)

마스터플랜 U1. 내용 없이 격자·병합·중첩만 복원시키고(정규화 방지 프롬프트),
skeletonize로 정답·예측을 같은 형식으로 깎아 TEDS-Struct로 채점한다.
thinking_level은 OpenRouter reasoning.effort(low|medium|high)로 조절.

LLM 입력 구성(system / few-shot / task / params)을 PROMPTS 레지스트리에 버전별로 보관한다.
VERSION을 바꾸면 결과가 u1/v<VERSION>/ 에 격리된다(같은 VERSION = 같은 입력 구성).
프롬프트를 새로 짜면 PROMPTS에 새 키를 추가하고 VERSION을 가리키게 한다 — 옛 버전 구성은 그대로 보존된다.

사용:
  python3.12 extract_u1.py s0-grid -t low      # 1장, 최소 사고 (현재 VERSION)
  python3.12 extract_u1.py -t low              # 전체 7장
  python3.12 extract_u1.py --rebuild-log       # API 호출 없이 _config.json·런로그만 재생성
출력:
  u1/v<N>/<id>.<level>.json   결과(teds + usage + 입력구성 + raw)
  u1/v<N>/<id>.<level>.html   모델 골격
  u1/v<N>/_config.json        이 버전의 LLM 입력 구성(상단 패널·런로그 공통 소스)
  runlog-v<N>.md              실행 로그 — 입력·출력 기록(사람용)
"""
import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
import urllib.request
import urllib.error
from pathlib import Path

from skeletonize import skeletonize
from teds import teds_struct_html

HERE = Path(__file__).parent
PNG = HERE / "png"
GT = HERE / "gt"
U1 = HERE / "u1"
MODEL = "google/gemini-3.1-pro-preview"

# ── 입력 구성 레지스트리 ──────────────────────────────────────────────────────
# 프롬프트(system/few-shot/task)·파라미터를 버전 키로 보관한다.
# VERSION이 가리키는 구성만 이번 실행에 쓰이고, 결과는 u1/v<VERSION>/ 에 격리된다.

# v1 — 최초(평문 규칙 나열). zero-shot.
SYSTEM_V1 = """너는 표 이미지의 '구조 골격'을 그대로 복원하는 정밀 도구다.
셀 내용(텍스트)은 모두 빈칸으로 두고, <table>의 골격만 HTML로 출력한다.
설명·머리말·코드펜스 없이 <table>...</table> 만 출력한다."""

TASK_V1 = """이 이미지의 표 구조를 빈 셀 HTML 골격으로 복원하라.

규칙:
- 셀 안의 텍스트는 절대 옮기지 마라. 모든 셀은 빈 <td></td> 로 둔다.
- 보이는 병합을 rowspan/colspan 속성으로 그대로 표현하라. 격자를 가지런하게 다듬지 마라.
- 표 안에 표가 있으면 <td> 안에 중첩 <table>로 표현하라. 깊이 제한 없이 재귀.
- 보이는 것에만 근거하라. 일반적인 표 형태를 가정해 칸을 채우거나 정리하지 마라.
- <th>/<td> 구분은 신경 쓰지 말고 전부 <td>로 써도 된다.

<table>...</table> 만 출력하라."""

# v1.1 — docs/prompt.md(Gemini 3) 충실 재구성.
#  중요지시 System 우선 배치 · XML 일관 구조 · 파라미터 정의 · 이미지 먼저/지시 끝 ·
#  출력 장황함 제어 · "충분히 살펴본 뒤 답하라". (정규화 자가검증은 의도적으로 배제.)
SYSTEM_V1_1 = """<role>
너는 문서 이미지 속 표의 '구조 골격'을 복원하는 정밀 변환 도구다.
표의 기하(행·열 격자, 병합, 중첩)만 다루고 셀의 내용에는 관여하지 않는다.
</role>

<definitions>
- 골격(skeleton): 표의 행·열 격자와 병합·중첩 관계만 남기고 텍스트·스타일을 제거한 구조.
- 셀(cell): 격자의 한 칸. 비어 있어도 하나의 셀로 센다.
- 병합(merge): 한 셀이 인접한 여러 칸을 덮는 것. 가로=colspan, 세로=rowspan.
- 중첩(nesting): 한 셀(<td>) 안에 또 다른 표(<table>)가 들어간 것.
</definitions>

<constraints>
- 셀 내용을 옮기지 않는다. 모든 셀은 빈 <td></td> 로 둔다.
- 보이는 격자선과 정렬만 근거로 삼는다. 흔한 표 형태를 가정해 칸을 채우거나 다듬지 않는다.
- 칸을 가르는 선이 실제로 보일 때만 별개의 셀로 나눈다. 보이는 병합만 colspan/rowspan으로 표기한다.
- 표 안의 표는 <td> 안에 중첩 <table>로 표현하고 깊이 제한 없이 재귀한다.
- <th>/<td>를 구분하지 않고 모두 <td>로 쓴다.
</constraints>

<output_format>
<table>...</table> 하나만 출력한다. 설명·머리말·코드펜스·주석을 붙이지 않는다.
</output_format>"""

TASK_V1_1 = """<task>
첨부한 이미지의 표 구조를 빈 셀 HTML 골격으로 복원하라.
</task>

<final_instruction>
이미지를 충분히 살펴본 뒤 답하라. 위 제약을 지켜 <table>...</table> 만 출력하라.
</final_instruction>"""

PROMPTS = {
    "1":   {"params": {"temperature": 1.0, "max_tokens": 16000},
            "system": SYSTEM_V1,   "task": TASK_V1,   "fewshot": []},
    "1.1": {"params": {"temperature": 1.0, "max_tokens": 16000},
            "system": SYSTEM_V1_1, "task": TASK_V1_1, "fewshot": []},
}

VERSION = "1.1"

_CFG = PROMPTS[VERSION]
SYSTEM = _CFG["system"]
TASK = _CFG["task"]
FEWSHOT = _CFG["fewshot"]
PARAMS = _CFG["params"]


def prompt_config() -> dict:
    """이 버전의 LLM 입력 구성 — 리포트 상단 패널·런로그가 공유하는 단일 소스."""
    return {
        "version": VERSION,
        "model": MODEL,
        "params": PARAMS,
        "system": SYSTEM,
        "task": TASK,
        "fewshot": FEWSHOT,
    }


def vdir() -> Path:
    d = U1 / f"v{VERSION}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    # 키는 repo_root/.env/.env 에 있음 (내용은 출력하지 않는다)
    envf = HERE.parents[1] / ".env" / ".env"
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("OPENROUTER_API_KEY 못 찾음 (.env/.env 확인)")


def img_part(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


def build_messages(img_path: Path) -> list:
    """system → (few-shot: 이미지+task / 정답출력) × N → 실제 입력(이미지 먼저, task 끝)."""
    msgs = [{"role": "system", "content": SYSTEM}]
    for ex in FEWSHOT:
        ex_img = Path(ex["image"]) if os.path.isabs(ex["image"]) else PNG / ex["image"]
        msgs.append({"role": "user", "content": [img_part(ex_img), {"type": "text", "text": TASK}]})
        msgs.append({"role": "assistant", "content": ex["output"]})
    msgs.append({"role": "user", "content": [img_part(img_path), {"type": "text", "text": TASK}]})
    return msgs


def call(img_path: Path, level: str, key: str) -> dict:
    payload = {
        "model": MODEL, **PARAMS,
        "reasoning": {"effort": level},
        "messages": build_messages(img_path),
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:600]}")


def clean_html(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:html)?\s*|\s*```$", "", t, flags=re.S)
    m = re.search(r"<table.*</table>", t, re.S | re.I)
    return m.group(0) if m else t


# ── 산출물 기록 ───────────────────────────────────────────────────────────────

def write_config() -> None:
    (vdir() / "_config.json").write_text(
        json.dumps(prompt_config(), ensure_ascii=False, indent=2), encoding="utf-8")


def _records() -> list:
    """이 버전 폴더의 결과 JSON을 (page, level 순)으로 로드."""
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
    u = rec.get("usage", {})
    rt = u.get("completion_tokens_details", {}).get("reasoning_tokens", "?")
    ts = rec.get("timestamp", "(기록 없음)")
    skel = rec.get("pred_skeleton", "")
    return (
        f"### {rec.get('page','?')} · thinking={rec.get('level','?')}\n\n"
        f"- 시각: {ts}\n"
        f"- 입력 이미지: `png/{rec.get('page','?')}.png` (+ 위 system·task 공통)\n"
        f"- TEDS-Struct: **{rec.get('teds_struct', float('nan')):.3f}**\n"
        f"- 토큰: total {u.get('total_tokens','?')} (reasoning {rt}) · ${u.get('cost','?')}\n\n"
        f"<details><summary>출력 골격 HTML</summary>\n\n```html\n{skel}\n```\n</details>\n"
    )


def rebuild_log() -> None:
    cfg = prompt_config()
    fs = cfg["fewshot"]
    if fs:
        fs_md = "\n".join(
            f"- 예시 {i+1}: 이미지 `{ex.get('image','?')}` → 출력\n\n```html\n{ex.get('output','')}\n```"
            for i, ex in enumerate(fs))
    else:
        fs_md = "(없음 — zero-shot)"
    header = (
        f"# U1 실행 로그 — v{VERSION}\n\n"
        f"표 이미지 → 빈 셀 골격 HTML 추출. model `{cfg['model']}` · "
        f"params `{json.dumps(cfg['params'], ensure_ascii=False)}` · thinking은 샘플별(low·medium·high).\n\n"
        f"아래 **LLM 입력 구성**은 이 버전 모든 호출에 공통이고, 입력 이미지만 샘플별로 바뀐다.\n\n"
        f"## LLM 입력 구성\n\n"
        f"<details open><summary>① system</summary>\n\n```\n{cfg['system']}\n```\n</details>\n\n"
        f"<details><summary>② few-shot ({len(fs)} shot)</summary>\n\n{fs_md}\n</details>\n\n"
        f"<details><summary>③ task (입력 지시 — 매 호출 이미지와 함께 전송)</summary>\n\n```\n{cfg['task']}\n```\n</details>\n\n"
        f"---\n\n## 호출 기록 (입력 → 출력)\n\n"
    )
    body = "\n".join(_log_entry(r) for r in _records()) or "_아직 결과 없음._\n"
    (vdir() / "runlog.md").write_text(header + body, encoding="utf-8")


def run_one(page: str, level: str, key: str) -> None:
    res = call(PNG / f"{page}.png", level, key)
    raw = res["choices"][0]["message"].get("content") or ""
    pred_html = clean_html(raw)
    pred_skel = skeletonize(pred_html)
    gt_skel = (GT / f"{page}.skeleton.html").read_text(encoding="utf-8")
    score = teds_struct_html(pred_skel, gt_skel)
    d = vdir()
    (d / f"{page}.{level}.html").write_text(pred_skel + "\n", encoding="utf-8")
    usage = res.get("usage", {})
    rec = {
        "page": page, "level": level, "version": VERSION,
        "model": MODEL, "params": PARAMS,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "teds_struct": score, "usage": usage,
        "system": SYSTEM, "task": TASK, "fewshot_n": len(FEWSHOT),
        "pred_skeleton": pred_skel, "raw": raw,
    }
    (d / f"{page}.{level}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    write_config()
    rebuild_log()
    rt = usage.get("completion_tokens_details", {}).get("reasoning_tokens", "?")
    print(f"{page:16} t={level:6} TEDS={score:.3f}  "
          f"reasoning={rt}tok total={usage.get('total_tokens','?')} ${usage.get('cost','?')}")


def main() -> None:
    if "--rebuild-log" in sys.argv:
        write_config()
        rebuild_log()
        print(f"✓ u1/v{VERSION}/_config.json · u1/v{VERSION}/runlog.md  ({len(_records())}건, API 호출 없음)")
        return
    key = load_key()
    # 위치인자(페이지)와 옵션(-t <level>)을 분리 — '-t' 다음 토큰은 값이므로 페이지로 안 센다.
    level = "low"
    pos = []
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-t":
            level = argv[i + 1]
            i += 2
            continue
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    pages = [pos[0]] if pos else [p.stem for p in sorted(PNG.glob("*.png"))]
    for page in pages:
        run_one(page, level, key)


if __name__ == "__main__":
    main()
