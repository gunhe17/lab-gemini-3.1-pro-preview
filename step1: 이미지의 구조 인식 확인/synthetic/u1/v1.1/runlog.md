# U1 실행 로그 — v1.1

표 이미지 → 빈 셀 골격 HTML 추출. model `google/gemini-3.1-pro-preview` · params `{"temperature": 1.0, "max_tokens": 16000}` · thinking은 샘플별(low·medium·high).

아래 **LLM 입력 구성**은 이 버전 모든 호출에 공통이고, 입력 이미지만 샘플별로 바뀐다.

## LLM 입력 구성

<details open><summary>① system</summary>

```
<role>
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
</output_format>
```
</details>

<details><summary>② few-shot (0 shot)</summary>

(없음 — zero-shot)
</details>

<details><summary>③ task (입력 지시 — 매 호출 이미지와 함께 전송)</summary>

```
<task>
첨부한 이미지의 표 구조를 빈 셀 HTML 골격으로 복원하라.
</task>

<final_instruction>
이미지를 충분히 살펴본 뒤 답하라. 위 제약을 지켜 <table>...</table> 만 출력하라.
</final_instruction>
```
</details>

---

## 호출 기록 (입력 → 출력)

### s0-grid · thinking=low

- 시각: 2026-06-04T14:02:17+09:00
- 입력 이미지: `png/s0-grid.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1661 (reasoning 0) · $0.004712

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
```
</details>

### s1-rowspan · thinking=low

- 시각: 2026-06-04T14:02:22+09:00
- 입력 이미지: `png/s1-rowspan.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1650 (reasoning 0) · $0.00445

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td rowspan="2"></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td rowspan="2"></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
```
</details>

### s2-multihead · thinking=low

- 시각: 2026-06-04T14:02:28+09:00
- 입력 이미지: `png/s2-multihead.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1641 (reasoning 0) · $0.004852

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td rowspan="2"></td>
    <td colspan="2"></td>
    <td colspan="2"></td>
    <td rowspan="2"></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
```
</details>

### s3-form-bands · thinking=low

- 시각: 2026-06-04T14:02:33+09:00
- 입력 이미지: `png/s3-form-bands.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1712 (reasoning 0) · $0.005574

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td colspan="6"></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td colspan="6"></td>
  </tr>
  <tr>
    <td rowspan="2"></td>
    <td colspan="5"></td>
  </tr>
  <tr>
    <td colspan="5"></td>
  </tr>
  <tr>
    <td></td>
    <td colspan="5"></td>
  </tr>
  <tr>
    <td></td>
    <td colspan="5"></td>
  </tr>
  <tr>
    <td colspan="6"></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
```
</details>

### s4-nested-asym · thinking=low

- 시각: 2026-06-04T14:02:40+09:00
- 입력 이미지: `png/s4-nested-asym.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1891 (reasoning 0) · $0.007762

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td rowspan="2"></td>
    <td></td>
    <td>
      <table>
        <tr>
          <td></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td>
      <table>
        <tr>
          <td></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td>
      <table>
        <tr>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td>
      <table>
        <tr>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td></td>
  </tr>
</table>
```
</details>

### s5-noruling · thinking=low

- 시각: 2026-06-04T14:02:51+09:00
- 입력 이미지: `png/s5-noruling.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 2408 (reasoning 729) · $0.013676

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td rowspan="2"></td>
    <td colspan="2"></td>
    <td colspan="2"></td>
    <td rowspan="2"></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
```
</details>

### s6-p011clone · thinking=low

- 시각: 2026-06-04T14:02:56+09:00
- 입력 이미지: `png/s6-p011clone.png` (+ 위 system·task 공통)
- TEDS-Struct: **0.875**
- 토큰: total 1641 (reasoning 0) · $0.004912

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
  </tr>
</table>
```
</details>

### s6-p011clone · thinking=medium

- 시각: 2026-06-04T14:01:05+09:00
- 입력 이미지: `png/s6-p011clone.png` (+ 위 system·task 공통)
- TEDS-Struct: **0.875**
- 토큰: total 3090 (reasoning 1467) · $0.0223

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
  </tr>
</table>
```
</details>

### s6-p011clone · thinking=high

- 시각: 2026-06-04T14:01:42+09:00
- 입력 이미지: `png/s6-p011clone.png` (+ 위 system·task 공통)
- TEDS-Struct: **0.875**
- 토큰: total 6167 (reasoning 4544) · $0.059224

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td></td>
    <td></td>
    <td></td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
    <td>
      <table>
        <tr>
          <td colspan="2"></td>
          <td></td>
        </tr>
        <tr>
          <td></td>
          <td></td>
          <td></td>
        </tr>
      </table>
    </td>
  </tr>
</table>
```
</details>
