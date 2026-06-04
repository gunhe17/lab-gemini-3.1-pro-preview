# PaddlePaddle — 우리 실험에 필요한 발췌

> 출처: [PaddlePaddle/Paddle](https://github.com/PaddlePaddle/Paddle) README + [Quick Install](https://www.paddlepaddle.org.cn/install/quick) (2026-06-04).
> 프레임워크 일반 기능(고차 자동미분·신경망 컴파일러·분산 자동병렬 등)은 표 구조 인식 평가와 무관 → 제외.
> **우리가 PaddleOCR-VL을 돌리며 실제로 부딪힌 것**만 추림.

## 1. 한 줄 정의 — 왜 보나
PaddlePaddle = 딥러닝 **프레임워크**(PyTorch/TensorFlow 대응). 우리가 평가하는 **PaddleOCR-VL**(표 구조 인식 전용 VL 파서)이 이 위에서 돈다.
→ 프레임워크 자체가 목적이 아니라, **"PaddleOCR-VL을 구동하는 런타임"**으로서만 필요. (프레임워크 ≠ 모델)

## 2. 설치 — 우리가 헤맨 핵심 지점
| 용도 | 명령 | 비고 |
|------|------|------|
| **CPU** | `pip install paddlepaddle` | PyPI. **arm64 macOS 지원**(로컬 M1에서 3.3.1 설치·import 확인). CUDA 미접촉 → 충돌 없음, 단 느림 |
| **GPU** | `pip install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/` | **PyPI 아님 — paddle 공식 인덱스**(PyPI엔 2.6.x뿐). 휠이 CUDA 런타임 번들 → 별도 CUDA 설치 불필요 |

- 최신 stable: **3.3** (우리는 PaddleOCR-VL 호환으로 3.2.2/3.3.1 사용).
- paddleocr는 별도: `pip install "paddleocr[doc-parser]"` (PyPI, **torch 불요** — 로컬 .venv-ocr에 torch 없이 동작 확인).

## 3. Colab 커널 사망의 정체 — 직접 겪은 함정
- `paddlepaddle-gpu`가 `nvidia-nccl-cu12`를 자기 핀(**2.25.1**)으로 깔아뭉갬 → Colab 기본 **torch**(nccl **2.28.9** 요구)가 `undefined symbol: ncclCommShrink`로 깨짐 → import/추론 시 **커널 세그폴트**.
- **해결**: PaddleOCR-VL은 torch가 필요 없으므로 →
  - GPU 경로: `pip uninstall -y torch torchvision torchaudio` **후** paddle-gpu 단독 설치 (충돌 상대 제거).
  - CPU 경로: 애초에 CUDA 미접촉이라 충돌 자체가 없음(가장 안전).

## 4. 메모리 — M1/8GB 한계 (실측)
- PaddleOCR-VL-1.6 (0.9B): 가중치 적재 ~**4GB**. **8GB에선 추론이 스왑 thrashing으로 멈춤**(CPU 6.6%·4.6분 무진행).
- 적재까지는 8GB에서 성공, **추론은 ≥12GB 필요**(Colab CPU에서 완료 확인).

## 5. 라이선스
- **Apache-2.0** (프레임워크). → 상업 도입 부담 낮음 — production 후보로서 의미.
  (MinerU도 최근 Apache 2.0 계열로 전환.)

---

### 한 줄 결론
PaddlePaddle은 **"PaddleOCR-VL 구동용 런타임"**으로만 우리에게 의미. 실전 포인트는 ③ 충돌 회피(torch 제거 or CPU)와 ④ 메모리(≥12GB) 두 가지. 모델 자체(아키텍처·OmniDocBench 수치·표 출력 포맷)는 PaddleOCR/HF 모델카드에 별도.
