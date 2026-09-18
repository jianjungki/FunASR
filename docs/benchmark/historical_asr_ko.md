# 과거 ASR 벤치마크 기록

[English](historical_asr.md) | [中文](historical_asr_zh.md) | [日本語](historical_asr_ja.md)

이 페이지는 이전 FunASR 비교를 참고하는 독자를 위해 **출처 정보가 불완전한 과거 기록**을 보존합니다.
새로운 측정, 범용 순위표, 현재 checkpoint·장비·배포에 대한 보장이 아닙니다.
대상 데이터는 **중국어 오디오**이며 이 한국어 페이지가 한국어나 일본어 인식 정확도를 측정한 것은 아닙니다.
새 평가를 시작할 때는 [성능 측정 방법(영문)](rtf_reproducibility.md)을 먼저 참고하세요.

## 과거 평가 요약

아래 표는 원래 한국어 페이지의 표현과 수치를 보존합니다.
"최고"와 같은 표현은 해당 보고서 안에서만 유효하며 모든 모델이나 하드웨어에 적용되지 않습니다.

| 항목 | 결과 |
| --- | --- |
| Dataset | 184개의 중국어 장문 오디오, 총 11,539초, 192.3분. |
| GPU | NVIDIA H100 80GB HBM3. |
| 최고 GPU 속도 | SenseVoice-Small: full benchmark에서 169.6x realtime, initial run에서 211.8x. |
| 최고 CPU 속도 | SenseVoice-Small: 17.2x realtime; Paraformer-Large: 15.6x realtime. |
| Baseline | OpenAI Whisper-large-v3: GPU에서 13.4x realtime. |

**전체 실행의 169.6x와 초기 실행의 211.8x는 따로 보고된 결과**입니다.
원래 페이지는 측정 날짜를 밝히지 않습니다. **2026-09-07은 출처 스냅샷을 확인한 날짜이지 측정일이 아닙니다**.

## 과거 평가 결과

이 표의 모든 수치와 설명은 원래 보고서의 과거 기록이며 **현재 API 기능에 대한 보장이 아닙니다**.
모델의 원시 출력에 태그가 있다는 사실이 HTTP 엔드포인트도 그 태그를 반환한다는 뜻은 아닙니다.
과거 타임스탬프 설명도 현재의 [모델 선택 가이드](../model_selection_ko.md)를 대신하지 않습니다.

| Model | Device | RTF | Speed | CER | Notes |
| --- | --- | --- | --- | --- | --- |
| SenseVoice-Small | GPU | 0.005896 | 169.6x | 7.81% | ASR + language / emotion / event tags; tag 제거 후 CER 계산. |
| Paraformer-Large | GPU | 0.008359 | 119.6x | 10.18% | VAD/punctuation pipeline과 잘 맞는 빠른 non-autoregressive 중국어 ASR. |
| Fun-ASR-Nano | GPU | 0.058803 | 17.0x | 8.06% | 중국어·영어·일본어, 7개 중국어 방언군, 26개 지역 억양을 지원하는 LLM-based ASR. hotword 지원. 신뢰할 수 있는 checkpoint-native timestamp는 미지원 ([#106](https://github.com/QwenAudio/Fun-ASR/issues/106)). |
| GLM-ASR-Nano | GPU | 0.026974 | 37.1x | 31.07% | LLM-based multilingual ASR. |
| Whisper-large-v3-turbo (OpenAI) | GPU | 0.021708 | 46.1x | 21.71% | OpenAI Whisper implementation. |
| Whisper-large-v3 (OpenAI) | GPU | 0.074694 | 13.4x | 20.02% | large Whisper quality 기준 baseline. |
| SenseVoice-Small | CPU | 0.057988 | 17.2x | 7.81% | remaining benchmark script에서 수집한 CPU run. |
| Paraformer-Large | CPU | 0.064056 | 15.6x | 10.18% | CPU batch job에도 활용 가능. |
| Fun-ASR-Nano | CPU | 0.274318 | 3.6x | 8.06% | LLM-based model은 더 무겁지만 realtime보다 빠릅니다. |

CPU/GPU 행에서 같은 CER가 반복된다고 해서 장치별로 독립적인 채점이 이루어졌다고 볼 수는 없습니다.
확인한 자료에는 원시 예측, 참조 텍스트, 채점 프로그램이 없습니다.
"태그 제거 후 CER 계산"은 과거의 주장으로 보존한 것이며 이번에 검증한 채점 결과가 아닙니다.
수치의 자릿수와 반올림된 속도·RTF 쌍은 다시 계산하지 않고 그대로 유지합니다.

## 출처와 한계

[원래 한국어 HTML](https://github.com/modelscope/FunASR/blob/67d63b80a246dc33749e43904c294e0409cd9183/ko/benchmark.html)은
과거 GitHub Pages 커밋에 고정되어 있습니다. 출처 확인 당시 이 파일은 보관된 공개 페이지 스냅샷과
바이트 단위로 같았습니다. 이는 표의 출처를 확인한 것이지 측정의 정확성이나 재현성을 증명한 것은 아닙니다.

원래 보고서는 RTF를 총 추론 시간과 총 오디오 길이의 비율로, 속도를 그 역수로 정의합니다.
속도는 RTFx라고도 합니다.

```text
RTF  = total inference time / total audio duration
RTFx = total audio duration / total inference time = 1 / RTF
```

다음 명령은 **과거 기록이며 확인한 체크아웃에서 그대로 실행할 수 없습니다**.
확인한 FunASR 소스 리비전 `386f6f9106684ba5a114e796147db4396a09eab5`에는
참조하는 세 파일이 모두 없습니다. 이 문서는 대체 스크립트나 재현용 데이터를 제공하지 않습니다.

```text
python benchmark/run_full_benchmark.py
python benchmark/run_remaining.py
python benchmark/fix_sensevoice_cer.py
```

원래 보고서는 CPU 모델·스레드 수, 데이터 구성과 참조 텍스트 목록, 정확한 checkpoint 리비전,
소프트웨어·드라이버 버전, 파일별 예측 및 시간 측정 로그를 공개하지 않습니다.
준비 실행, I/O, 전처리를 포함하는지 등 전체 측정 범위도 충분히 기록되어 있지 않습니다.
이 자료가 없으므로 표를 그대로 재현할 수 없으며 CPU와 GPU 비교를 모든 운영 환경에 일반화할 수도 없습니다.

이 기록의 **11,539초**와 [vLLM 측정 방법(영문)](rtf_reproducibility.md)의 **11,541초**는
구분해서 인용하세요. 두 기록이 모두 184개 파일을 언급해도 같은 파일 집합이라는 증거는 아닙니다.
두 표의 결과를 합치거나 2초 차이를 임의로 보정하지 마세요.

## 현재 모델 선택

다음은 **원래 추천 표를 과거의 맥락으로만 보존한 것**입니다.
새롭게 검증한 추천이나 성능 순위가 아닙니다.

| 필요한 것 | 추천 model |
| --- | --- |
| 가장 빠른 production transcription | SenseVoice-Small 또는 Paraformer-Large. |
| CPU batch transcription | 먼저 SenseVoice-Small; 중국어 production pipeline은 Paraformer-Large. |
| 중국어·영어·일본어 및 중국어 방언/억양 LLM-style recognition | Fun-ASR-Nano. 31개 언어는 별도 checkpoint인 [Fun-ASR-MLT-Nano](https://huggingface.co/FunAudioLLM/Fun-ASR-MLT-Nano-2512)를 사용하고, LLM decoding throughput이 중요하면 [vLLM](../vllm_guide.md). |
| OpenAI 호환 local endpoint | [funasr-server](../agent_integration_ko.md)와 model alias `sensevoice`, `paraformer`, `fun-asr-nano`. |

현재의 판단에는 [모델 선택](../model_selection_ko.md), [Agent 인터페이스와 제약](../agent_integration_ko.md),
[배포 방식](../deployment_matrix_ko.md), [vLLM 가이드(영문)](../vllm_guide.md)를 사용하세요.
별도 checkpoint인 MLT-Nano의 31개 언어 범위를 기본 Fun-ASR-Nano에 적용하지 마세요.
대상 언어, 직접 사용할 오디오, 실행 환경, 종단 간 지연 시간을 평가한 뒤 배포 방식을 선택하세요.
공식 native vLLM과 split-engine은 checkpoint와 API가 다르므로 서로 바꾸어 사용하면 안 됩니다.

새로운 측정에는 [성능 측정 방법(영문)](rtf_reproducibility.md)을, 동시 접속 실시간 서비스에는
[WebSocket 벤치마크(영문)](realtime_ws_benchmark.md)를 참고하세요.
현재 [마이그레이션 시간 측정 도구](../../examples/migration/benchmark_funasr.py)는 직접 준비한 오디오에서
FunASR의 실행 시간을 측정할 뿐, **CER/WER를 계산하지 않고 Whisper를 실행하지 않으며
누락된 과거 스크립트를 재현하지도 않습니다**.
측정 범위, 실패한 파일, 품질 평가는 구분해서 명시하세요.
