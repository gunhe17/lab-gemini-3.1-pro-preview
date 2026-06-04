# U1 실행 로그 — v1

표 이미지 → 빈 셀 골격 HTML 추출. model `google/gemini-3.1-pro-preview` · params `{"temperature": 1.0, "max_tokens": 16000}` · thinking은 샘플별(low·medium·high).

아래 **LLM 입력 구성**은 이 버전 모든 호출에 공통이고, 입력 이미지만 샘플별로 바뀐다.

## LLM 입력 구성

<details open><summary>① system</summary>

```
너는 표 이미지의 '구조 골격'을 그대로 복원하는 정밀 도구다.
셀 내용(텍스트)은 모두 빈칸으로 두고, <table>의 골격만 HTML로 출력한다.
설명·머리말·코드펜스 없이 <table>...</table> 만 출력한다.
```
</details>

<details><summary>② few-shot (0 shot)</summary>

(없음 — zero-shot)
</details>

<details><summary>③ task (입력 지시 — 매 호출 이미지와 함께 전송)</summary>

```
이 이미지의 표 구조를 빈 셀 HTML 골격으로 복원하라.

규칙:
- 셀 안의 텍스트는 절대 옮기지 마라. 모든 셀은 빈 <td></td> 로 둔다.
- 보이는 병합을 rowspan/colspan 속성으로 그대로 표현하라. 격자를 가지런하게 다듬지 마라.
- 표 안에 표가 있으면 <td> 안에 중첩 <table>로 표현하라. 깊이 제한 없이 재귀.
- 보이는 것에만 근거하라. 일반적인 표 형태를 가정해 칸을 채우거나 정리하지 마라.
- <th>/<td> 구분은 신경 쓰지 말고 전부 <td>로 써도 된다.

<table>...</table> 만 출력하라.
```
</details>

---

## 호출 기록 (입력 → 출력)

### s0-grid · thinking=low

- 시각: (기록 없음)
- 입력 이미지: `png/s0-grid.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1466 (reasoning 0) · $0.004382

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

- 시각: (기록 없음)
- 입력 이미지: `png/s1-rowspan.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1449 (reasoning 0) · $0.004048

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

- 시각: (기록 없음)
- 입력 이미지: `png/s2-multihead.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1440 (reasoning 0) · $0.00445

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

- 시각: (기록 없음)
- 입력 이미지: `png/s3-form-bands.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1523 (reasoning 0) · $0.005316

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

- 시각: (기록 없음)
- 입력 이미지: `png/s4-nested-asym.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1690 (reasoning 0) · $0.00736

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

- 시각: (기록 없음)
- 입력 이미지: `png/s5-noruling.png` (+ 위 system·task 공통)
- TEDS-Struct: **1.000**
- 토큰: total 1450 (reasoning 0) · $0.00419

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

- 시각: (기록 없음)
- 입력 이미지: `png/s6-p011clone.png` (+ 위 system·task 공통)
- TEDS-Struct: **0.219**
- 토큰: total 1419 (reasoning 0) · $0.004258

<details><summary>출력 골격 HTML</summary>

```html
<table>
  <tr>
    <td rowspan="4"></td>
    <td rowspan="4"></td>
    <td rowspan="4"></td>
    <td colspan="3"></td>
    <td colspan="3"></td>
  </tr>
  <tr>
    <td colspan="2"></td>
    <td rowspan="2"></td>
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
    <td colspan="3"></td>
    <td colspan="3"></td>
  </tr>
</table>
```
</details>

### s6-p011clone · thinking=medium

- 시각: (기록 없음)
- 입력 이미지: `png/s6-p011clone.png` (+ 위 system·task 공통)
- TEDS-Struct: **0.875**
- 토큰: total 3380 (reasoning 1958) · $0.02779

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

- 시각: (기록 없음)
- 입력 이미지: `png/s6-p011clone.png` (+ 위 system·task 공통)
- TEDS-Struct: **0.875**
- 토큰: total 5568 (reasoning 4146) · $0.054046

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
