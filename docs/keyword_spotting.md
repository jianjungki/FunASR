[简体中文](keyword_spotting_zh.md) | English

# Keyword Spotting

Detect a configured keyword in one utterance with a KWS checkpoint. This task
does not produce a general transcription, speaker identity, or wake-word
timestamps. **The streaming SANM Python interface returns results at utterance
end, not wake events for every incoming packet.**

## Choose the Matching Path

| Task | Guide |
| --- | --- |
| Detect keywords in a complete recording | [FSMN KWS examples](../examples/industrial_data_pretraining/fsmn_kws) |
| Feed packets, then detect at utterance end | SANM recipe below |
| Transcribe general speech continuously | [Streaming ASR SDK](python_api.md#streaming-cache-lifecycle) |
| Locate speech activity | [Streaming VAD](streaming_vad.md) |

FSMN uses its own checkpoint tokenizer and vocabulary, not streaming SANM cache
settings. The SANM recipe below uses the online checkpoint and `小云小云`.
ASR text/hotwords are not a KWS detector; VAD finds speech boundaries, not keywords.

Changing `keywords` configures decoder candidates; it does not train a model
for any arbitrary phrase or language. Use checkpoint-supported tokens, inspect
its model card and license, and evaluate each intended keyword on your audio.
Use a nonempty string, with ASCII commas separating multiple keywords, not a
Python list or the ASR `hotword` parameter. Detection is not a list of every
keyword occurrence. The offline FSMN example uses
`iic/speech_charctc_kws_phone-xiaoyun`, not an invented `fsmn-kws` alias.
The [Model Zoo](../model_zoo/readme.md) and individual training recipes remain
the source for other architectures; their interfaces are not interchangeable.

## Pin a Source Version

This recipe requires the fixes merged in [#3655](https://github.com/modelscope/FunASR/pull/3655)
and [#3656](https://github.com/modelscope/FunASR/pull/3656). **PyPI `funasr==1.4.14`
does not include them.** After the [environment checks](installation/installation.md),
install the exact tested source in your isolated environment:

```sh
python -m pip uninstall -y funasr
python -m pip install "funasr @ git+https://github.com/modelscope/FunASR.git@403555289a6d4f79f5c4a48e5beb00f521c5e172"
```

The uninstall step replaces an already installed package with the same version
number; a Git URL or `--upgrade` alone may leave that older package installed.
Run these commands in the isolated environment, not a shared production worker.

A source checkout may still report package version `1.4.14`; record the Git
commit and actual imported module path as well as the package version. A later release must explicitly include
both fixes before substituting its wheel. This guide is not a new PyPI release.

Prepare a complete local snapshot of
`iic/speech_sanm_kws_phone-xiaoyun-commands-online`, including configuration,
tokenizer, frontend/CMVN files and weights. Record the resolved revision or a
file checksum manifest; a moving `master` label is not an immutable revision.
Use a nonempty mono 16 kHz WAV. No download occurs inside the example.
For external arrays, use normalized one-dimensional `float32` samples, not
integer PCM. Resample the complete signal before splitting it; independent
per-packet resampling is not covered by the continuity guarantee.

## Run a File or Ordered Packets

The program takes `model_dir`, `audio`, and optional `--mode file` (default:
`stream`). Stream mode reads a complete WAV and simulates 960-sample packets;
it is not a microphone client and holds the file in memory. `detect_stream` is
an application helper, not a new SDK method.

```python
import argparse
from pathlib import Path
import soundfile as sf
from funasr import AutoModel


def detect_stream(model, speech, sample_rate, packet_samples=960):
    if packet_samples <= 0 or len(speech) == 0:
        raise ValueError("Audio length and packet size must be positive")
    cache = {}
    final_results = []
    for start in range(0, len(speech), packet_samples):
        end = min(start + packet_samples, len(speech))
        final_results = model.generate(
            input=speech[start:end], fs=sample_rate, cache=cache,
            chunk_size=[4, 8, 4], batch_size=1, is_final=end == len(speech),
        )
    return final_results


parser = argparse.ArgumentParser()
parser.add_argument("model_dir")
parser.add_argument("audio")
parser.add_argument("--mode", choices=["file", "stream"], default="stream")
args = parser.parse_args()
model_dir = Path(args.model_dir).expanduser().resolve(strict=True)
if not model_dir.is_dir():
    raise ValueError("Expected a complete local SANM KWS model directory")
speech, sample_rate = sf.read(args.audio, dtype="float32")
if sample_rate != 16000 or speech.ndim != 1 or len(speech) == 0:
    raise ValueError("Expected nonempty mono 16 kHz audio")

model = AutoModel(
    model=str(model_dir), keywords="小云小云", device="cpu", ncpu=1,
    chunk_size=[4, 8, 4], encoder_chunk_look_back=0,
    decoder_chunk_look_back=0, disable_update=True, trust_remote_code=False,
)
if args.mode == "file":
    results = model.generate(
        input=args.audio, fs=sample_rate, cache={}, chunk_size=[4, 8, 4],
        batch_size=1, is_final=True,
    )
else:
    results = detect_stream(model, speech, sample_rate)
for item in results:
    print(item["text"])
```

## Read Results and Manage Sessions

- Nonfinal public `AutoModel.generate` calls return `[]`. This means no final
  result yet, not a rejected keyword. Final results contain `key` and `text`;
  the text is `detected <keyword> <score>` or `rejected`. The score is not a
  calibrated probability or a universal operating threshold. No time interval
  or speaker identity is returned.
  If the entire utterance has no valid feature frames, its final result can
  also be `[]`; absence of a result is not evidence of rejection. An empty EOS
  still decodes output accumulated from earlier packets.
- `chunk_size=[4, 8, 4]` specifies left/current/right **frontend feature frames**,
  not milliseconds or caller packet lengths. The example's 960 samples equal
  60 ms at 16 kHz; this is an input packet duration, not measured wake latency.
  Keep model, keyword, chunk settings and sample rate fixed within a session.
- Share the same dictionary only across ordered calls for one utterance. Use
  `batch_size=1` and a fresh cache for another recording or cancelled session.
  Separate caches alone do not make concurrent calls on one `AutoModel`
  thread-safe; serialize calls or isolate model workers.
- The last nonempty packet in this example carries `is_final=True`, even for
  exact packet multiples. With the pinned SANM fixes, a single empty **array**
  final call after nonfinal audio also flushes pending state. Do not resend
  consumed audio, add a second EOS after finalization, or assume other models
  share this behavior. File/URL inputs are whole utterances and finalize
  automatically; do not use repeated file paths as streaming packets.
- Finalization resets this model's cache fields in place; they need not become
  an empty dictionary. Discard session state at the application boundary anyway.
  Encoded output accumulates until EOS: impose explicit utterance limits, not
  an unbounded always-on session. Choosing VAD or a timeout for those limits is
  application policy and changes which audio the detector sees.
- Omitting `output_dir` now returns results without creating a result writer.
  If output files are wanted, explicitly configure a writable `output_dir`;
  result files are optional and may append across calls. They are not required
  for inference and are not an event delivery system.

## Evidence and Deployment Limits

The source fix was checked on CPU with the official checkpoint, one official
positive sample and synthetic silence. Under one thread and frontend `dither=0`,
the complete file, complete array, 960-sample packets and irregular packets
with empty EOS produced identical final encoder frames for the positive sample.
The baseline and fixed version both detected the keyword; silence was rejected.
This is a continuity regression check, **not** an accuracy improvement, a
natural-negative false-accept benchmark, or a microphone/GPU validation.
The example leaves the checkpoint frontend configuration intact; bitwise
comparisons require the same deterministic settings used in that check.

The Python example does not establish KWS support in the transcription HTTP
server, native vLLM, llama.cpp or the C++ WebSocket protocol. Check the separate
[deployment matrix](deployment_matrix.md) and a runtime's model contract before
building a service. Do not route KWS result strings as OpenAI transcription text
or advertise immediate wake events that this implementation does not emit.

For a bug report, retain the original audio, model manifest, source commit,
packet lengths/order, finalization flags and result strings. Include natural
negative recordings and your false-accept/false-reject methodology before
claiming deployment accuracy. Do not post secrets or private audio publicly.

Source contracts: [streaming implementation](../funasr/models/sanm_kws_streaming/model.py),
[optional output tests](../tests/test_kws_optional_output.py),
[stream continuity tests](../tests/test_kws_streaming_continuity.py), and
[runnable guide tests](../tests/test_kws_docs.py). Guide tests execute the
published entry point with a recording SDK double; they do not load weights.
