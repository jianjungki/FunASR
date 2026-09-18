# FunASR Agent 연동

[English](agent_integration.md) | [中文](agent_integration_zh.md) | [日本語](agent_integration_ja.md)

애플리케이션에 필요한 인터페이스를 선택하세요. HTTP 파일 전사, 로컬 MCP 도구,
데스크톱 녹음, 로컬 자막 파이프라인은 지원 모델, 옵션, 반환 필드가 모두 같지 않습니다.
프로세스 안에서 직접 추론하려면 [Python SDK(영문)](python_api.md)를 사용하세요.

## HTTP 서버

다음은 뒤에서 사용할 예제 스크립트까지 포함하는 소스 기반 준비 절차입니다.
POSIX 셸에서 새 체크아웃과 가상 환경을 사용하세요.
PyPI 패키지만 설치하면 이 저장소의 예제 스크립트가 함께 배치되지는 않습니다.

```bash
git clone https://github.com/modelscope/FunASR.git FunASR-agent
cd FunASR-agent
git checkout --detach e19029adca384a06a2f60bd8c18cb98f1a0499aa
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install fastapi uvicorn python-multipart
python -m pip check
```

이 절차는 소스 리비전만 고정하며 모든 의존 패키지와 모델 가중치를 고정하지는 않습니다.
[설치 가이드(영문)](installation/installation.md)에 따라 CPU/GPU 환경을 준비하고,
실제 패키지 및 모델 버전을 기록한 뒤 대상 모델로 요청을 검증하세요.
`pip check`만으로 CUDA, 오디오 디코더, 새 환경 설치가 정상임을 확인할 수는 없습니다.

준비된 환경에서 다음 명령 중 **하나만** 실행하세요. CPU 예제는 SenseVoice를 명시적으로 선택합니다.
CUDA 대안에는 작동하는 GPU 환경이 필요합니다. 서버 터미널을 유지하고,
클라이언트는 별도로 준비한 다른 터미널에서 실행하세요.

```bash
funasr-server --host 127.0.0.1 --device cpu --model sensevoice --port 8000
# Alternative: stop the CPU server before using the same port.
funasr-server --host 127.0.0.1 --device cuda --model sensevoice --port 8000
```

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models
```

- 파일 업로드에는 `/v1/audio/transcriptions`를 사용합니다.
- 실행 중인 서비스의 스키마는 `/openapi.json`에 있습니다.
- Swagger UI는 `/docs`에 있습니다. 이 경로는 FunASR 웹사이트의 문서 디렉터리가 아닙니다.

상태 확인이나 모델 목록 응답이 성공해도 대상 모델의 실제 전사가 성공했다는 뜻은 아닙니다.

패키지의 `funasr-server`와 [예제 HTTP 서버(영문)](../examples/openai_api/README.md#api-contract)는
기본값, 별칭, 응답 스키마가 다릅니다. 시작할 때뿐 아니라 요청에도 `model`을 지정하세요.
`paraformer-en`은 예제 서버의 별칭이며 패키지 서버의 내장 별칭이 아닙니다.
사용자 지정 모델은 적절한 `--hub`와 `--model-path`로 설정하고 요청에는 `model="custom"`을 사용하세요.
임의의 모델 ID가 자동으로 `--model`의 내장 별칭이 되는 것은 아닙니다.

SenseVoice의 HTTP 표시 텍스트에서는 리치 태그가 제거됩니다.
이 서비스는 감정이나 이벤트를 전용 필드로 반환하는 API가 아닙니다.
기본 Fun-ASR-Nano는 중국어·영어·일본어 및 중국어 방언·지역 억양의 평가 경로이고,
31개 언어를 다루는 Fun-ASR-MLT-Nano는 **별도 checkpoint**입니다.
기본 Nano의 범위가 한국어 지원을 뜻하지 않으며, HTTP 인터페이스만으로 타임스탬프를 보장할 수도 없습니다.
[모델 선택](model_selection_ko.md)과 [배포 방식](deployment_matrix_ko.md)에서 실제 경로를 확인하세요.

[MOSS-Transcribe-Diarize(영문)](moss_transcribe_diarize.md)는 OpenMOSS가 제공하는 제3자 모델이며
별도의 배포 요건이 있습니다. 네이티브 화자 라벨은 녹음 내 익명 라벨이지 실제 인물의 신원이 아닙니다.
외부 VAD나 외부 화자 모델이 필요하지 않으므로 해당 단계를 추가하지 마세요.
모든 클라이언트가 모델의 전체 출력을 표시한다고 가정해서도 안 됩니다.

로컬 서버는 아래 SDK의 임시 API 키를 인증하지 않습니다.
네트워크에 공개하기 전에 [보안 가이드(영문)](../examples/openai_api/SECURITY.md)에 따라
TLS, 인증, 업로드 크기 제한, 요청 속도 제한을 추가하세요. CORS는 인증이 아닙니다.

## SDK와 curl

클라이언트 환경에 별도의 OpenAI HTTP 클라이언트를 설치합니다.

```bash
python -m pip install openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-development")
with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="sensevoice",
        file=audio,
        response_format="verbose_json",
    )
print(result.text)
for segment in getattr(result, "segments", []):
    print(segment)
```

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

`verbose_json`은 응답 형식만 선택합니다. 화자 분리를 켜거나 리치 태그를 복구하지 않으며,
단어 단위 시각이나 정렬도 보장하지 않습니다. 예제 서버는 기존 `sentence_info`를 segments로
옮기고, 해당 정보가 없으면 빈 목록을 반환합니다. 패키지 서버는 대략적인 대체 구간을 만들 수 있습니다.
두 서버 모두 segment 시각을 초 단위로 반환하지만 `duration` 필드의 의미는 다릅니다.
시각을 사용하기 전에 [클라이언트 응답 계약(영문)](../examples/openai_api/CLIENTS.md#response-formats)을 확인하세요.
`json`과 `text`는 더 단순한 응답 형식입니다.
`spk=true` 화자 처리는 패키지 API에 속하며 예제 서버의 요청 스키마에는 없습니다.
[화자 라벨과 신원 식별의 차이(영문)](speaker_emotion.md)도 참고하세요.

## 워크플로 연동

Dify/n8n 등의 HTTP 노드에서 전사 엔드포인트로 `POST` multipart 요청을 보냅니다.
바이너리 파일 필드 이름은 `file`이고 텍스트 필드는 `model`과 `response_format`입니다.
`file` 필드에 오디오 URL을 넣는 것은 오디오 바이트를 업로드하는 것과 다릅니다.
컨테이너 안의 `localhost`는 FunASR 호스트가 아니라 해당 컨테이너 자신을 가리킵니다.
의도한 게이트웨이를 통해 접근 가능한 서비스 주소를 설정하세요.

- [Dify, n8n, webhook worker(영문)](../examples/openai_api/WORKFLOWS.md): 요청 연결 예제.
- [JavaScript / TypeScript(영문)](../examples/openai_api/JAVASCRIPT.md): SDK 및 multipart 클라이언트.
- [Postman(영문)](../examples/openai_api/POSTMAN.md)과 [스모크 테스트](../examples/openai_api/smoke_test.py): 배포된 엔드포인트 확인.
- [Gradio(영문)](../examples/openai_api/GRADIO.md): 브라우저 업로드 및 마이크 입력.
- [OpenAPI(영문)](../examples/openai_api/OPENAPI.md): 저장소 예제 스키마와 실행 중인 패키지 서비스 스키마의 차이.

이 요청 및 응답 범위에 맞춰 호스트 프레임워크에 전사 도구를 등록하세요.
URL worker 예제는 완전한 보안 기능을 갖춘 다운로더가 아닙니다.
신뢰할 수 없는 URL을 받기 전에 목적지 허용 목록, 사설 네트워크 접근 차단,
리디렉션 검증, 크기 제한과 타임아웃을 추가하세요.
워크플로 필드 표가 두 서버 모두에 그대로 적용된다고 가정하지 말고 위의 응답 계약을 사용하세요.
이 예제는 모든 프레임워크 버전의 연동이 검증되었다는 증거나 임의의 URL이 안전하다는 보장이 아닙니다.

## MCP 서버

준비된 저장소 루트와 환경에서 실행합니다.

```bash
python examples/mcp_server/funasr_mcp.py
```

전사 전에 설치 가이드에 따라 PyTorch와 호환되는 오디오 특징 추출 백엔드를 준비하세요.
툴킷 설치나 MCP 핸드셰이크 성공만으로 모델 실행이 검증되지는 않습니다.
이 스크립트에는 추가 MCP SDK 패키지가 필요하지 않습니다.
MCP 클라이언트가 HTTP가 아닌 stdio로 스크립트를 시작합니다.
준비된 Python 환경과 체크아웃의 절대 경로를 설정하세요.

```json
{
  "mcpServers": {
    "funasr": {
      "command": "/path/to/FunASR-agent/.venv/bin/python",
      "args": ["/path/to/FunASR-agent/examples/mcp_server/funasr_mcp.py"],
      "env": {
        "FUNASR_DEVICE": "cpu",
        "FUNASR_MODEL": "iic/SenseVoiceSmall"
      }
    }
  }
}
```

`transcribe_audio`는 서버에서 볼 수 있는 기존 로컬 `audio_path`를 받습니다.
컨테이너에 읽기 전용으로 마운트된 경로도 사용할 수 있지만 URL이나 실시간 스트림은 받지 않습니다.
첫 호출에서 가중치를 다운로드하고 로드할 수 있습니다.
언어 힌트는 `auto`, `zh`, `yue`, `en`, `ja`, `ko`입니다.
`FUNASR_MODEL`을 바꾸어도 도구 스키마가 바뀌지 않으며 다른 모델이 해당 VAD 경로와 호환된다는 보장도 없습니다.

결과는 MCP `content`의 `type=text`로 형식화되며 선택적으로 구간 정보를 포함합니다.
HTTP 응답 객체가 아닙니다. 최상위 전사 텍스트에서 리치 태그를 제거하지만,
선택적 구간 텍스트는 모델 출력에서 복사합니다.
`FUNASR_DEVICE`의 기본값은 `cpu`, `FUNASR_MODEL`의 기본값은 `iic/SenseVoiceSmall`입니다.
[MCP 소스와 컨테이너 설정](../examples/mcp_server/README.md)에서 클라이언트 설정과 마운트 방법을 확인하세요.
어시스턴트와 서버가 접근할 수 있는 파일을 제한해야 합니다. 로컬 도구 자체가 파일 시스템 권한 경계는 아닙니다.

## 데스크톱 음성 입력

HTTP 서버를 실행한 상태에서 준비된 체크아웃의 다른 터미널을 사용합니다.

```bash
python -m pip install sounddevice numpy pyperclip openai pynput
python examples/voice_input/funasr_input.py --server http://localhost:8000/v1 --model sensevoice
```

스크립트는 녹음을 시작하거나 중지하고, WAV를 HTTP 서비스에 업로드한 뒤 전사 텍스트를 복사합니다.
마이크 권한과 오디오 장치 지원이 필요합니다. macOS에서는 손쉬운 사용 권한도 필요할 수 있으며,
Linux의 자동 붙여넣기는 `xdotool`을 사용합니다. 클립보드와 붙여넣기 동작은 데스크톱 세션에 따라 달라집니다.
현재 `--lang` 옵션은 파싱되지만 전사 요청에 전달되지 않아 이 경로에서 유효한 언어 제어 옵션이 아닙니다.

원격 `--server`를 지정하면 녹음이 해당 엔드포인트로 전송됩니다.
항상 완전히 오프라인이거나 오디오가 기기를 벗어나지 않는다는 보장, 고정 지연 시간 보장은 없습니다.
배포 전에 [설정 옵션](../examples/voice_input/README.md#配置选项)과
[구현](../examples/voice_input/funasr_input.py)을 확인하세요.

## 자막 생성

이것은 로컬 `AutoModel` 파이프라인이며 HTTP나 MCP 클라이언트가 아닙니다.
준비된 체크아웃에서 로컬 입력 파일과 적절한 추론 환경을 사용합니다.

```bash
python examples/subtitle/generate_subtitle.py video.mp4
python examples/subtitle/generate_subtitle.py meeting.wav --spk
python examples/subtitle/generate_subtitle.py podcast.mp3 --format vtt
python examples/subtitle/generate_subtitle.py audio.wav --device cpu
```

기본 장치는 CUDA이고 마지막 명령은 CPU를 명시적으로 선택합니다.
기본 모델은 SenseVoiceSmall이며 VAD와 문장부호 모델을 함께 사용합니다.
이 고정 파이프라인은 임의의 모델에 적용할 수 있는 범용 실행법이 아닙니다.
`--spk`는 CAM++ 익명 화자 라벨을 추가하지만 실제 신원을 확인하지 않습니다.
`--format`은 SRT/VTT를 선택하고 `--output`은 출력 경로를 지정합니다.
**기존 출력 파일은 덮어씁니다**. 이전 자막을 보존하려면 다른 경로를 지정하세요.
`--lang`은 `auto`가 아닌 언어 힌트를 추론에 전달합니다.
`--max-single-segment-time`의 단위는 밀리초이며 현재 기본값은 `60000`입니다.

`--segment-mode readable`은 인식 텍스트나 문장부호를 다시 쓰지 않고 표시용 자막을 묶습니다.
`sentence`는 모델의 원래 문장 구분을 유지합니다. 두 모드 모두 문장부호 오류를 고치거나 음소 경계를 보장하지 않습니다.
실제 타임스탬프가 있는지 확인하고 원본 오디오와 재생을 대조하세요.
시간 정보가 없으면 길이가 0인 `(0, 0)` 구간으로 대체될 수 있으며, 이는 유효성이 검증된 자막이 아닙니다.
입력 디코딩, 모델 및 의존 패키지 로딩, GPU 용량은 환경별로 검증해야 합니다.
출력 해석은 [자막 옵션(영문)](../examples/subtitle/README.md#options)과
[화자 가이드(영문)](speaker_emotion.md)를 참고하세요.
