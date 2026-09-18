[简体中文](streaming_vad_zh.md) | English

# Streaming Voice Activity Detection

Use FSMN VAD to receive speech-start and speech-end events while feeding one
recording in order. VAD does not transcribe speech, identify speakers, or locate
linguistic sentence boundaries. For a first offline VAD call, use the
[SDK tutorial](tutorial/README.md); for streaming ASR, use the separate
[Paraformer cache example](python_api.md#streaming-cache-lifecycle).

## Prepare the Model and Audio

Complete the [installation checks](installation/installation.md). Prepare a
complete local snapshot of `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`,
including configuration, frontend files and weights. Record the resolved model
revision and review its model license. This recipe expects that 16 kHz checkpoint,
not an arbitrary VAD model or a streaming ASR checkpoint.

Use a nonempty mono 16 kHz WAV. The program below takes the local model directory
and audio path as its two positional command-line arguments. It reads the file
once and simulates ordered streaming chunks; it is not microphone capture or a
WebSocket service. The entire file remains in memory.

## Interpret Events

Each returned dictionary has a `value` list. Every pair uses **milliseconds
relative to the beginning of this stream**, not the current input chunk.
Do not add the chunk offset a second time.

| Event | Meaning |
| --- | --- |
| `[]` | No new boundary; an earlier speech span may still be open. |
| `[[start, -1]]` | A speech span started; retain the start for a later call. |
| `[[-1, end]]` | The previously started span ended. |
| `[[start, end]]` | Both boundaries are available in this call. |

One call can return several pairs. `-1` is a missing-boundary sentinel, never a
timestamp to pass to a waveform slice. Keep the pending start per stream.
The strict example below reports unexpected event order instead of inventing
a missing start or silently overwriting one.

## Run Ordered Chunks

The two small helpers are application-side example code, not new FunASR APIs.
The last **nonempty** chunk carries `is_final=True`, including when the input
length is exactly a multiple of the stride.

```python
import argparse
from pathlib import Path
import soundfile as sf
from funasr import AutoModel


def chunk_ranges(length, stride):
    if length <= 0 or stride <= 0:
        raise ValueError("Audio length and chunk stride must be positive")
    for start in range(0, length, stride):
        end = min(start + stride, length)
        yield start, end, end == length


def consume_events(events, pending_start):
    spans = []
    for start_ms, end_ms in events:
        if start_ms < 0 and end_ms < 0:
            raise ValueError("An event must provide a boundary")
        if start_ms >= 0:
            if pending_start is not None:
                raise ValueError("New start before the previous speech span ended")
            pending_start = start_ms
        if end_ms >= 0:
            if pending_start is None or end_ms < pending_start:
                raise ValueError("End without a matching earlier start")
            spans.append((pending_start, end_ms))
            pending_start = None
    return pending_start, spans


parser = argparse.ArgumentParser()
parser.add_argument("model_dir")
parser.add_argument("audio")
args = parser.parse_args()
model_dir = Path(args.model_dir).expanduser().resolve(strict=True)
if not model_dir.is_dir():
    raise ValueError("Expected a complete local FSMN VAD model directory")
speech, sample_rate = sf.read(args.audio, dtype="float32")
if sample_rate != 16000 or speech.ndim != 1 or len(speech) == 0:
    raise ValueError("Expected nonempty mono 16 kHz audio")

model = AutoModel(
    model=str(model_dir), device="cpu", ncpu=4,
    disable_update=True, trust_remote_code=False,
)
chunk_ms = 200
stride = sample_rate * chunk_ms // 1000
cache = {}
pending_start = None
for start, end, final in chunk_ranges(len(speech), stride):
    results = model.generate(
        input=speech[start:end], fs=sample_rate, cache=cache,
        chunk_size=chunk_ms, is_streaming_input=True, is_final=final,
        batch_size=1, dynamic_silence=False,
    )
    for item in results:
        pending_start, spans = consume_events(item.get("value", []), pending_start)
        for start_ms, end_ms in spans:
            print(start_ms, end_ms)
if pending_start is not None:
    print("Unclosed speech start (ms):", pending_start)
# End this session; never share its cache with another recording.
cache = {}
```

At 16 kHz, `chunk_size=200` means 200 ms, or 3200 input samples. It is a
scalar duration for FSMN VAD, not Paraformer streaming's three-element
`chunk_size` list. Keep the same cache dictionary and chunk settings during
a stream, use `batch_size=1`, and create a new cache for every other recording,
user or cancelled session. This implementation reinitializes its cache after a
nonempty final call; discard it at the application boundary anyway.

Do not append an empty final call to flush this example: the current
[inference path](../funasr/models/fsmn_vad_streaming/model.py) returns early for
empty input, before its normal finalization path. For live input whose end is
not known in advance, hold the latest nonempty chunk. When the next chunk
arrives, submit the held chunk with `is_final=False` and hold the new one.
Only when end-of-stream arrives, submit the held chunk with `is_final=True`.
That strategy adds one chunk of input buffering; do not resend an already
consumed chunk. Cancelling a session instead discards its held audio and cache.

## Tune Only After Measuring

The example explicitly sets `is_streaming_input=True` to avoid the
implementation's mode default depending on `chunk_size`. It also sets
`dynamic_silence=False` to keep checkpoint/configured end-silence settings
instead of the current dynamic schedule. This is a reproducibility choice,
not a recommended threshold or a latency guarantee. Inspect
`max_end_silence_time`, `max_single_segment_time` and model configuration
before tuning; their durations are milliseconds. Input chunk duration is not
the total detection latency or a promise of phonetic boundary accuracy.

Keep raw boundary events, model/SDK revisions, configuration and the original
audio when investigating clipping. A missing or late boundary is not fixed by
globally padding every segment. If a final start remains unclosed, report it;
do not fabricate an end at the recording duration.

## SDK and Deployment Boundaries

- This recipe emits boundaries, not ASR text or subtitles. Combining VAD, ASR,
  punctuation and speakers has a different [SDK pipeline contract](python_api.md).
- Python cache events are not a C++ server wire protocol; use the
  [WebSocket protocol](../runtime/docs/websocket_protocol.md) for that service.
- Third-party OpenMOSS [MOSS-Transcribe-Diarize](moss_transcribe_diarize.md)
  provides its own joint transcription/diarization path. Do not add this external
  VAD stage as an assumed prerequisite.
- Source references: [upstream demo](../examples/industrial_data_pretraining/fsmn_vad_streaming/demo.py),
  [model implementation](../funasr/models/fsmn_vad_streaming/model.py),
  [buffer tests](../tests/test_fsmn_vad_streaming_buffers.py) and
  [dynamic-silence tests](../tests/test_dynamic_streaming_vad.py).
  [Recipe tests](../tests/test_streaming_vad_docs.py) execute chunk arithmetic and
  event assembly without downloading weights; they are not acoustic accuracy,
  live microphone, or deployment benchmarks.
