([English](README.md)|[简体中文](README_zh.md)|[日本語](README_ja.md)|한국어)

# FunASR OpenAI 호환 API 서버

FunASR OpenAI 호환 API는 음성 파일을 multipart HTTP로 보내는 `/v1/audio/transcriptions`를 제공합니다. 음성 전사용 OpenAI API의 일부를 구현한 것이며, 전체 API, 실시간 API 또는 모든 SDK와 프레임워크 기능의 호환성을 보장하지 않습니다.

이 페이지는 저장소의 [예제 서비스](server.py)를 실행하는 방법입니다. 패키지의 `funasr-server`는 [다른 구현](../../funasr/bin/_server_app.py)이므로 설정을 재사용하기 전에 [API 계약](#api-contract)을 확인하세요. [한국어 Agent 가이드](../../docs/agent_integration_ko.md)는 패키지 서비스와 여러 연동 방식의 시작점입니다. 프로세스 안에서 `AutoModel.generate()`를 호출하려면 Python SDK 가이드의 [영문판](../../docs/python_api.md) 또는 [중문판](../../docs/python_api_zh.md)을 참고하세요.

**로컬 개발 환경에서 시작하세요.** 이 서비스에는 인증 기능이나 애플리케이션 수준의 업로드 크기 상한이 내장되어 있지 않으며 SDK의 임시 API 키도 인증하지 않습니다. 아래 명령은 호스트의 loopback 주소에 명시적으로 바인딩합니다. 공유하거나 공개하기 전에 [보안 및 게이트웨이 가이드](SECURITY.md)에 따라 TLS, 인증, 업로드 크기 제한, 요청 속도 제한, 클라이언트와 게이트웨이의 타임아웃을 설정하세요. 음성 및 전사문의 보관 기간과 접근 권한을 정하고 `/health`, `/v1/models`, `/openapi.json` 및 Swagger UI `/docs`에 대한 접근도 제한하세요. CORS는 인증을 대신하지 않습니다.

## API Contract

- **예제 `server.py`**: 시작 시 미리 로드하는 모델과 multipart `model` 생략 시 기본값은 모두 `sensevoice`입니다. 폼은 `file`, `model`, `language`, `response_format`을 받습니다. 아래에서는 `json` 또는 `verbose_json`을 사용합니다.
- **패키지 `funasr-server`**: CLI 기본값인 `--model auto`는 장치 문자열이 `cuda`로 시작하면 `fun-asr-nano`, 아니면 `sensevoice`를 선택합니다. 반면 multipart `model`을 생략하면 미리 로드한 모델과 관계없이 `fun-asr-nano`가 선택됩니다.

요청마다 `model`을 명시하고 실행 중인 `/v1/models`와 `/openapi.json`을 확인하세요. `paraformer-en`은 예제 서비스에 등록되어 있지만 패키지 서비스의 내장 별칭은 아닙니다. 패키지 서비스에서 사용자 지정 모델을 쓰려면 `--model-path`와 적절한 `--hub`를 설정하고 요청에 `model="custom"`을 사용하세요. 이 CLI 옵션들은 예제 `server.py`에는 없습니다. 임의의 checkpoint ID를 `--model`에 넣을 수 있다는 뜻도 아닙니다.

`response_format=verbose_json`은 응답 형식 선택이며, **화자 분리나 타임스탬프 생성을 켜는 옵션이 아닙니다**. 예제 서비스는 모델이 반환한 `sentence_info`만 `segments`로 변환하고, 없으면 `segments=[]`를 반환합니다. SDK에 `timestamps`나 `ctc_timestamps`가 있어도 이를 직접 HTTP `segments`로 내보내는 처리는 아닙니다. Nano의 CTC 시각 정보는 필요한 학습 가중치가 모두 있는지에 따라 달라지며, HTTP에서 항상 얻을 수 있는 것은 아닙니다.

예제에는 `spk` 폼 필드가 없습니다. `spk=true`를 보내도 외부 화자 처리가 활성화되지 않습니다. 패키지 서비스에서는 `spk=true`로 네이티브 화자 분리 모델 외의 모델에 별도 화자 처리를 요청할 수 있습니다. 기본값은 `False`이며 해당 의존 환경과 모델이 필요합니다. MOSS의 네이티브 출력은 녹음 안의 익명 라벨이지 실제 인물의 신원이나 서로 다른 녹음 사이의 동일 인물 판정이 아닙니다. MOSS에 외부 VAD나 화자 모델을 추가하지 마세요.

두 서비스의 `start` / `end` 단위는 초입니다. SDK의 `sentence_info`에 있는 밀리초 좌표는 HTTP 어댑터에서 초로 변환합니다. 예제의 `duration`은 첫 모델 로드를 제외한 `generate()` 처리 시간이며, **음성 길이가 아닙니다**. 예제의 `language`는 전달한 힌트 또는 생략 시 `auto`이며 언어 감지 결과라고 볼 수 없습니다. 패키지 서비스의 `duration`은 음성 길이이고, fallback 경로에서 메타데이터를 읽지 못하면 0이 될 수 있습니다. `language`는 `auto`가 아닌 명시적 힌트를 우선하며, 없으면 얻을 수 있는 감지 결과를 사용합니다. 패키지 서비스의 fallback은 텍스트와 음성 길이로 대략적인 구간을 만들 수도 있으므로 단어 단위 강제 정렬 결과가 아닙니다.

패키지의 verbose 응답에는 `task`와 구간별 `id` / `words`가 있고, 예제 응답에는 `model`이 있습니다. 화자 필드는 없거나 null일 수 있습니다. 완전히 같은 JSON 스키마라고 가정하지 말고 [응답 예시와 화자 요청](CLIENTS.md#api-contract)을 확인하세요. `language` 힌트의 의미도 모델에 따라 다릅니다. SDK의 `use_itn`, `hotwords`, 캐시, 배열 입력 등은 이 HTTP 폼의 옵션이 아니며 `AutoModel.generate()`의 모든 기능이 노출되는 것은 아닙니다.

## 빠른 시작

POSIX 셸과 Python 3.11을 사용해 새 체크아웃과 가상 환경을 만드세요. PyPI 패키지만 설치하면 저장소의 예제 파일은 함께 배치되지 않습니다.

```bash
git clone https://github.com/modelscope/FunASR.git FunASR-api
cd FunASR-api
git checkout --detach d91d961e37a005837b1523bcc6b09f087877be54
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install fastapi uvicorn python-multipart
python -m pip check
cd examples/openai_api
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

이 절차는 소스 revision만 고정합니다. 의존 패키지, 모델 가중치, 오디오 디코더, CUDA 환경까지 고정하지는 않습니다. [설치 가이드](../../docs/installation/installation.md)에 따라 대상 환경을 준비하세요. 버전이 `1.4.14`로 표시되어도 배포된 PyPI 패키지와 수정된 소스의 내용이 같다는 뜻은 아닙니다. `pip check`는 의존성 선언의 일관성을 확인하며, 새 환경 설치나 음성 추론의 성공을 증명하지 않습니다.

CUDA를 사용하려면 호환되는 PyTorch와 드라이버 등을 준비한 뒤 CPU 서버를 중지하고, 같은 가상 환경의 `examples/openai_api` 디렉터리에서 다음 대체 명령을 실행하세요. 같은 포트에 두 서버를 동시에 실행하지 마세요.

```bash
python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000
```

모델 로드가 끝날 때까지 기다리고 서버 터미널은 유지하세요. 첫 다운로드와 시작 시간은 checkpoint, 캐시, 네트워크, 하드웨어에 따라 달라집니다. 이후 클라이언트 작업은 다른 터미널에서 합니다. 처음 `git clone`을 실행한 상위 디렉터리에서 같은 환경과 작업 디렉터리로 들어가세요.

```bash
cd FunASR-api
source .venv/bin/activate
cd examples/openai_api
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models
curl -fsS http://localhost:8000/openapi.json
```

상태 확인이나 모델 목록 조회의 성공만으로 음성 전사가 성공했는지는 알 수 없습니다. 별도 설명이 없으면 이후 클라이언트 명령은 이 디렉터리에서 실행하세요.

바로 복사해서 쓸 수 있는 연동 예제가 필요하면 [클라이언트 레시피](CLIENTS.md), [JavaScript/TypeScript 레시피](JAVASCRIPT.md), [Gradio 브라우저 데모](GRADIO.md), [워크플로 레시피](WORKFLOWS.md), [Postman 컬렉션](POSTMAN.md), [OpenAPI 명세](OPENAPI.md), [보안 및 게이트웨이 가이드](SECURITY.md), [Kubernetes 배포 템플릿](kubernetes/README.md)을 참고하세요.

### 엔드투엔드 smoke test

위에서 준비한 클라이언트 터미널에서 다음 중 하나를 실행할 수 있습니다. 이는 검증 절차이며 대상 환경에서 이미 실행한 결과를 제시하는 것이 아닙니다.

```bash
bash smoke_test.sh
# curl/bash가 없는 환경을 위한 크로스 플랫폼 방식:
python smoke_test.py
```

수동으로 확인하려면 다음 공개 샘플을 사용할 수 있습니다. 이 파일은 **중국어 음성**이며, 이 샘플의 전사는 일본어나 한국어 정확도 검증이 아닙니다.

```bash
curl -fL https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/BAC009S0764W0121.wav -o sample.wav
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@sample.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## Gradio 브라우저 데모

로컬 파일을 업로드하거나 마이크로 녹음한 음성을 보내려면 유지 관리되는 [Gradio 브라우저 데모](GRADIO.md)를 참고하세요. 이 API 서버와 별도의 Python 3.12 환경 `.venv-gradio`를 사용합니다. 가이드에서는 `funasr`, `vllm`, `sglang-omni` profiles, 명시적 모델 선택, Docker/Kubernetes 연결, 마이크 권한과 개인정보 보호상의 제한을 다룹니다. UI는 별도의 HTTP 클라이언트이며 인증 게이트웨이나 실시간 전사 서비스가 아닙니다.

## OpenAI SDK로 사용하기

OpenAI HTTP 클라이언트를 별도로 설치하세요. 이것은 FunASR의 프로세스 내 Python SDK가 아닙니다.

```bash
python -m pip install openai
```

`meeting.wav`를 실제 로컬 음성 파일로 바꿔 실행하세요. 디코딩 가능한 형식은 준비한 오디오 의존 환경에도 영향을 받습니다. 임시 `api_key`는 SDK의 필수 인자를 채우는 값이지 예제 서비스가 수행하는 인증이 아닙니다.

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="sensevoice",
        file=audio,
    )
print(result.text)

with open("meeting.wav", "rb") as audio:
    verbose = client.audio.transcriptions.create(
        model="sensevoice",
        file=audio,
        response_format="verbose_json",
    )
print(getattr(verbose, "segments", []))
```

구간 배열은 비어 있을 수 있습니다. 구간이 반환되어도 그것만으로 정확한 자막 시각이나 화자 분리를 확인할 수는 없습니다. [API 계약](#api-contract)을 참고하세요.

## curl로 사용하기

`audio.wav`는 실제 로컬 음성 파일로 바꾸세요. JSON에 배열이나 URL을 넣는 방식이 아니라, `file`에 바이너리 파일을 multipart로 보냅니다.

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice

curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## 사용 가능한 모델

다음은 예제 `server.py`의 `MODEL_CONFIGS`에 있는 5개 별칭입니다. 전체 SDK나 모든 서버의 공통 모델 목록이 아니며, 일정한 처리 속도나 동시 처리량을 보장하는 표도 아닙니다.

- `sensevoice`: SenseVoiceSmall + FSMN-VAD. 기본적으로 문장 타임스탬프나 외부 화자 클러스터링을 활성화하지 않습니다.
- `paraformer`: `paraformer-zh` + FSMN-VAD + CT 문장부호 모델. 문장부호 처리가 설정되어 있지만 `verbose_json`만으로 문장별 기록을 요청하지는 않습니다.
- `paraformer-en`: `paraformer-en` + FSMN-VAD. 이 예제에는 문장부호 모델이 설정되어 있지 않으며 패키지 서비스의 내장 별칭도 아닙니다.
- `fun-asr-nano`: HF의 Fun-ASR-Nano를 `AutoModel` + FSMN-VAD로 사용합니다. 이 예제는 vLLM 경로가 아니며 CTC 시각이 HTTP 구간으로 반환된다는 보장도 없습니다.
- `moss-transcribe-diarize`: 제3자 OpenMOSS의 네이티브 전사 및 화자 분리 어댑터. 별도 의존 환경이 필요하며 모델이 반환한 시각과 익명 화자 라벨을 유지합니다.

SenseVoice의 HTTP 텍스트에서는 `<|...|>` 리치 태그가 제거됩니다. 감정이나 이벤트를 전용 필드로 반환하는 API가 아닙니다. 원시 모델 출력이 필요하면 모델별 Python SDK 계약을 확인하세요.

기본 Fun-ASR-Nano는 중국어·영어·일본어 및 중국어 방언·지역 억양을 다루는 경로이며 한국어 지원을 포함한다는 뜻이 아닙니다. 31개 언어를 지원하는 **Fun-ASR-MLT-Nano는 별도 checkpoint**이고, 두 서비스의 내장 별칭이 아닙니다. 대상 언어와 모델 가중치의 라이선스는 [모델 선택 가이드](../../docs/model_selection_ko.md)와 개별 모델 카드에서 확인하세요. FunASR 소프트웨어의 MIT 라이선스가 모든 모델 가중치의 라이선스를 뜻하지는 않습니다.

MOSS는 고정 revision의 third-party HF model을 사용하며 외부 VAD / speaker model과 결합하지 않습니다. 라벨은 녹음 안의 익명 화자를 나타내며 사람의 신원을 검증하지 않습니다. `funasr-server`, Docker, Kubernetes, vLLM, SGLang Omni, LocalAI, FunClip의 개별 경로는 [MOSS deployment guide](../../docs/moss_transcribe_diarize.md)를 참고하세요. 별칭이 목록에 있다는 것만으로 모든 모델의 로드 완료나 의존 환경의 호환성을 확인할 수는 없습니다.

## API 엔드포인트

| Endpoint | Method | 설명 |
|---|---|---|
| `/v1/audio/transcriptions` | POST | OpenAI 호환 음성 전사 |
| `/v1/models` | GET | 모델 별칭 목록 |
| `/health` | GET | 헬스 체크, 로드된 모델, 사용 가능한 모델 |
| `/docs` | GET | FastAPI Swagger 문서 |
| `/openapi.json` | GET | 실행 중인 서비스의 스키마 |

코드 작성 없이 확인하려면 [Gradio 브라우저 데모](GRADIO.md)로 로컬 업로드나 마이크 테스트를 진행하거나 [Postman 컬렉션](POSTMAN.md)을 가져오세요. [OpenAPI 명세](OPENAPI.md)는 예제용 자료이지 패키지 서비스의 모든 필드를 설명하는 자료가 아닙니다. API 게이트웨이나 클라이언트 생성에는 실행 중인 스키마도 확인하세요.

## 에이전트 및 로우코드 워크플로

**LangChain**, **LlamaIndex**, **AutoGen**, **CrewAI**, **Semantic Kernel**, **Dify**, **n8n** 등에는 multipart HTTP 또는 도구 함수를 통해 연결할 수 있습니다. 사용하는 버전과 이 서비스의 필드를 기준으로 개별 확인하세요. 모든 프레임워크 기능이나 실시간 API의 호환성을 보장하지 않습니다.

두 서비스는 n8n용 특수 요청 별칭 `whisper-1`을 시작 시 선택한 모델로 매핑합니다. OpenAI Whisper를 실행하라는 지정이 아닙니다. 패키지 서비스에 `--model-path`를 지정했다면 `custom`으로 매핑됩니다. 일반 HTTP 노드에서는 `model`을 명시하고 이 호환 별칭을 임의의 모델 전환 기능으로 취급하지 마세요.

Dify/n8n의 파일은 multipart 바이너리 `file`로 전달합니다. 컨테이너 안의 `localhost`는 그 컨테이너 자신입니다. 허가된 서비스 이름이나 접근 가능한 호스트를 설정하고, 연결 문제를 해결하려고 인증 없이 공개하지 마세요. URL을 가져오는 worker를 사용한다면 대상 검증과 크기 제한도 별도로 필요합니다.

- SDK, JavaScript/TypeScript, Agent tool 작성법은 [클라이언트 레시피](CLIENTS.md)와 [JavaScript/TypeScript 레시피](JAVASCRIPT.md)를 참고하세요.
- Dify, n8n, HTTP 노드, webhook worker는 [워크플로 레시피](WORKFLOWS.md)를 참고하세요.
- GUI smoke test는 [Postman 컬렉션](POSTMAN.md)을 참고하세요.
- schema 기반 가져오기는 [OpenAPI 명세](OPENAPI.md)를 사용할 수 있습니다.

## Docker 배포

저장소 루트에서 다음 명령을 실행하세요. 호스트 서버가 이미 실행 중이면 중지해 포트를 비워 두세요. 기본 이미지는 예제 `server.py`를 CPU 모드로 시작하며 패키지의 `funasr-server`를 실행하지 않습니다.

Dockerfile은 버전이 고정되지 않은 PyPI FunASR와 의존 패키지를 설치하고 체크아웃의 `server.py`를 복사합니다. 앞의 소스 고정 및 editable install과 같은 환경이 아니며, 재현 가능한 모델 검증을 마친 이미지라고 볼 수도 없습니다.

```bash
cd examples/openai_api
cp .env.example .env

FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build
```

이 POSIX 셸 접두 설정은 기존 Compose 파일의 호스트 공개 포트를 loopback으로 제한합니다. 컨테이너 내부 리스너는 `0.0.0.0`을 유지하세요. 컨테이너 리스너를 `127.0.0.1`로 바꾸는 것과는 다릅니다. 호스트 loopback은 로컬 개발 설정이지 인증이나 전체 네트워크의 안전성을 보장하는 기능이 아닙니다.

Compose와 동시에 실행하지 않을 때 사용할 `docker run` 명령:

```bash
docker build -t funasr-api .

docker run --rm -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cpu \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

GPU 호스트에서는 NVIDIA Container Toolkit과 CUDA 지원 PyTorch/FunASR 이미지가 필요합니다. CUDA 의존성에 맞게 이미지를 조정한 뒤 다음처럼 실행할 수 있습니다.

```bash
docker run --rm --gpus all -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cuda \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

컨테이너가 시작되면 같은 환경과 예제 디렉터리를 준비한 다른 터미널에서 다음 중 하나로 확인할 수 있습니다:

```bash
BASE_URL=http://localhost:8000 bash smoke_test.sh
python smoke_test.py --base-url http://localhost:8000
```

추가 build/run/smoke 절차는 [validate_docker.sh](validate_docker.sh)에 있지만, **기본적으로 호스트의 모든 인터페이스에 포트를 공개**하며 위의 loopback 설정을 상속하지 않습니다. 실행 전에 네트워크 설정을 확인하고 공유 네트워크의 로컬 검증에는 위의 명시적인 loopback 절차를 사용하세요. GPU 모드에는 CUDA 지원 이미지와 NVIDIA Container Toolkit이 필요합니다. 이 페이지의 설명은 Docker나 음성 추론의 실행 완료 증거가 아닙니다.

## Kubernetes 배포

팀에서 공유하거나 게이트웨이를 통해 노출하기 전에 [보안 및 게이트웨이 가이드](SECURITY.md)를 검토하고 TLS, 인증, 업로드 제한, 속도 제한, 타임아웃, 로그와 보관 기간 정책을 준비하세요.

영구 모델 캐시, 헬스 프로브, 프라이빗 `ClusterIP`를 갖춘 내부 클러스터 서비스가 필요하다면 [Kubernetes 배포 템플릿](kubernetes/README.md)에서 시작하세요. 예제 이미지를 빌드하고 push한 뒤 manifests를 적용하고, `kubectl port-forward`와 `python smoke_test.py --base-url http://localhost:8000`으로 검증합니다.

CUDA 지원 이미지와 GPU 스케줄링 설정이 준비되기 전까지는 기본 CPU 모드를 유지하세요.

## 설정

다음은 예제 `server.py`의 기본값이며 `funasr-server`의 기본값이 아닙니다. [API 계약](#api-contract)과 비교하세요. 로컬 절차에서는 안전을 위해 `--host 127.0.0.1`과 `--device cpu`를 명시합니다.

| 인자 | 기본값 | 설명 |
|---|---|---|
| `--host` | `0.0.0.0` | 바인드 주소 |
| `--port` | `8000` | 포트 |
| `--device` | `cuda` | `cuda`, `cpu`, `mps` |
| `--model` | `sensevoice` | 시작 시 미리 로드할 모델 |

Docker 환경 변수:

| Env | 기본값 | 설명 |
|---|---|---|
| `FUNASR_PORT` | `8000` | `server.py`로 전달되는 컨테이너 포트 |
| `FUNASR_DEVICE` | `cpu` | 컨테이너 디바이스 모드. CUDA 지원 의존성이 포함된 이미지에서만 `cuda`로 설정하세요 |
| `FUNASR_MODEL` | `sensevoice` | 컨테이너 시작 시 로드할 모델 별칭 |
| `FUNASR_HOST_PORT` | `8000` | Compose의 호스트 포트 지정. 위 로컬 절차에서는 `127.0.0.1:8000`을 사용합니다. |

## 문제 해결

| 증상 | 해결 방법 |
|---|---|
| CUDA를 사용할 수 없음 | 먼저 `--device cpu`로 smoke test를 통과시키세요. |
| 8000 포트가 사용 중 | `--port 9000`으로 바꾸고 `BASE_URL=http://localhost:9000 bash smoke_test.sh` 또는 `python smoke_test.py --base-url http://localhost:9000`을 실행하세요. |
| 모델 다운로드가 느림 | 안정적인 네트워크에서 다시 시도하거나 ModelScope/Hugging Face에서 모델을 미리 다운로드하세요. |
| Dify/n8n 컨테이너에서 `localhost` 접속 실패 | 허가된 호스트명, Compose service name 또는 Kubernetes service name을 사용하고 접근 제어를 유지하세요. |
| 응답에 `segments`가 없음 | `response_format=verbose_json`으로 구간 필드가 있는 형식을 선택할 수 있지만 배열은 비어 있을 수 있습니다. 타임스탬프나 화자 분리를 켜는 지정이 아닙니다. [API 계약](#api-contract)을 확인하세요. |
