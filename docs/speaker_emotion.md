[简体中文](speaker_emotion_zh.md) | English

# Speakers and Emotion Tags

Choose the result you need before choosing the model. A speaker embedding,
an anonymous cluster label, an enrolled person's identity and an emotion tag
are different outputs. None can be substituted for another.

## Choose a Task

| Task | Path |
| --- | --- |
| Extract one speaker vector from selected speech | CAMPPlus or ERes2NetV2; example below |
| Attribute transcript segments to anonymous speakers | [ASR/VAD/speaker pipeline](python_api.md#vad-timestamps-and-speakers) |
| Preserve transcription, emotion and event tags | SenseVoiceSmall; example below |
| Joint transcription and anonymous diarization | Third-party [OpenMOSS MOSS guide](moss_transcribe_diarize.md) |

CAMPPlus and ERes2NetV2 return `spk_embedding`, a Tensor, not a person's name,
match decision or general ASR `text` field. A single input normally has one row;
its embedding dimension comes from the checkpoint configuration, not a universal
192-element API guarantee. Use `batch_size=1` here: some batching paths return
multiple embedding rows in one dictionary, not one keyed result per input.

Embeddings alone do not establish identity. Enrollment, matching, threshold
calibration, consent and evaluation on the intended population are separate
application work. A clustering label such as `spk=0` or MOSS's `S01` is anonymous
within a recording, not a stable person ID across recordings. A requested
`spk_embedding_center` is a cluster mean, not completed enrollment.

## Prepare a Local Checkpoint

Complete the [installation checks](installation/installation.md) and use a
complete local snapshot with its configuration, frontend, tokenizer where
applicable, and weights. Review each model's license and record the resolved
revision or file hashes, SDK version, imported module path and source commit.
This guide follows the implementations linked below; it does not claim that
every older wheel, export or model variant has the same interface.

- **CAMPPlus (`embedding`):** `iic/speech_campplus_sv_zh-cn_16k-common`.
  Its ModelScope alias is `cam++`.
- **ERes2NetV2 (`embedding`):** `iic/speech_eres2netv2_sv_zh-cn_16k-common`.
- **SenseVoice (`sensevoice`):** `iic/SenseVoiceSmall`.

The `embedding` and `sensevoice` choices belong to this example program, not new
FunASR model aliases or CLI subcommands. Do not point `embedding` at an ASR
checkpoint or generalize ERes2NetV2 behavior to every ERes2Net variant.
Check [Model Zoo](../model_zoo/readme.md) for other model paths.

Use nonempty mono 16 kHz WAV audio. The program reads normalized `float32`
samples and rejects stereo, empty or differently sampled audio instead of
silently transforming it. For embeddings, select a single person's speech;
mixtures, silence and extremely short clips are not reliable identity evidence.
The input checks below are format checks, not a speech-quality detector.

## Save the SDK Result Without Losing Tags

This standalone program takes `task`, `model_dir`, `audio` and a new JSON output
path. For example, run it with `embedding /models/campplus speaker.wav vector.json`
or `sensevoice /models/sensevoice utterance.wav tags.json` after the script name.
Both modes process a complete clip on CPU, without VAD, punctuation, a companion
speaker model or streaming cache. There are no model downloads in the program.

```python
import argparse
import json
import os
from pathlib import Path
import soundfile as sf
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


def embedding_record(results):
    if not results:
        raise ValueError("No result from the speaker model")
    if len(results) != 1:
        raise ValueError("Expected one speaker result for one input")
    vector = results[0]["spk_embedding"]
    if vector.ndim != 2 or vector.shape[0] != 1 or vector.shape[1] == 0:
        raise ValueError("Expected a nonempty single-row speaker embedding")
    return {"spk_embedding": vector.detach().cpu().tolist()}


def tagged_records(results):
    if not results:
        raise ValueError("No result from SenseVoice")
    records = []
    for item in results:
        raw = item["text"]
        if not isinstance(raw, str):
            raise ValueError("Expected SenseVoice text with its original tags")
        records.append({
            "key": item.get("key"), "raw_tagged_text": raw,
            "display_text": rich_transcription_postprocess(raw),
        })
    return records


def write_result(path, record):
    payload = json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(payload + "\n")


parser = argparse.ArgumentParser()
parser.add_argument("task", choices=["embedding", "sensevoice"])
parser.add_argument("model_dir")
parser.add_argument("audio")
parser.add_argument("output")
args = parser.parse_args()
model_dir = Path(args.model_dir).expanduser().resolve(strict=True)
if not model_dir.is_dir():
    raise ValueError("Expected a complete local model directory")
speech, sample_rate = sf.read(args.audio, dtype="float32")
if sample_rate != 16000 or speech.ndim != 1 or len(speech) == 0:
    raise ValueError("Expected nonempty mono 16 kHz audio")
model = AutoModel(
    model=str(model_dir), device="cpu", ncpu=1, disable_update=True,
    trust_remote_code=False, vad_model=None, punc_model=None, spk_model=None,
)
if args.task == "embedding":
    results = model.generate(input=speech, fs=sample_rate, batch_size=1)
    result = embedding_record(results)
else:
    results = model.generate(
        input=speech, fs=sample_rate, batch_size=1,
        language="auto", use_itn=True, output_timestamp=False,
    )
    result = tagged_records(results)
write_result(args.output, {
    "task": args.task, "model_dir": str(model_dir),
    "sample_rate": sample_rate, "result": result,
})
```

The JSON envelope, `raw_tagged_text` and `display_text` are application-owned
fields created by this example, not new SDK response fields. The vector is
explicitly detached, moved to CPU and converted to a nested list for JSON.
Nonfinite numeric values are rejected before creating a file. Existing output
files are never overwritten; select a new path for each run. On POSIX the file
is created with owner-only mode; use appropriate directory permissions and
platform ACLs too. Voice-derived vectors and transcripts can be sensitive:
retain only what the application needs and do not post private samples publicly.

## Read SenseVoice Tags Correctly

The raw tagged string is normally in `result["text"]`, not a guaranteed
`raw_text`, `emotion` or `emotion_score` field. Tags are case-sensitive, for
example `<|zh|>`, `<|HAPPY|>`, `<|Speech|>` and `<|withitn|>`. Their presence and
meaning depend on the checkpoint. A presentation mapping table is not a promise
that every model emits every mapped tag.

`rich_transcription_postprocess` is lossy display processing: it removes tags,
chooses display emotion by occurrence counts and merges repeated display
markers. It also performs text replacements. It is neither a structured tag
parser nor a probability calculator; preserve the original string first.
Do not infer confidence, psychological state or diagnosis from a display symbol
or model label. Silence and short/noisy clips are not reliable emotional evidence.
`emotion2vec` is a separate model/interface, not an alias for SenseVoice tags.

The example chooses `language="auto"`, `use_itn=True` and
`output_timestamp=False` explicitly; these are not all mandatory parameters.
SenseVoice language hints use `auto/zh/en/yue/ja/ko`. `use_itn` controls inverse
text normalization, not emotion recognition, and explicit `text_norm` takes
precedence. Repeat request options on each call. This is whole-clip inference,
not the KWS EOS protocol or a live emotional-state monitor.

## VAD, Diarization and Service Boundaries

Standalone embedding extraction and short-clip SenseVoice inference do not
require VAD. Generic AutoModel speaker clustering instead lives in its VAD
pipeline: setting only `spk_model` or `return_spk_res=True` does not add
diarization to direct inference. VAD boundaries are not guaranteed speaker
changes. Long-audio segmentation also changes the context used for tags.
Follow the separate [SDK pipeline](python_api.md#vad-timestamps-and-speakers)
for compatible ASR/VAD/punctuation/speaker models. `sentence_info[].spk` is
anonymous and its SDK `start/end` fields use milliseconds; NumPy cluster-center
arrays need explicit serialization just like tensors.

Third-party OpenMOSS MOSS-Transcribe-Diarize supplies its own joint transcription
and diarization path without an external `vad_model` or `spk_model`. Reuse the
[MOSS guide](moss_transcribe_diarize.md) for backend, memory and response details;
do not attach a second clustering pipeline or advertise known-person identity.

The current built-in [HTTP transcription service](../examples/openai_api/README.md)
configures SenseVoice with VAD and its fallback strips rich tags from top-level
and segment text. It does not add emotion score fields. Its `spk=true` path is
a service-specific pipeline, and HTTP segment `start/end` use seconds. Moving
this SDK example to `/v1/audio/transcriptions` is not a promise to preserve its
tags or parameters. Check the [deployment matrix](deployment_matrix.md) rather
than assuming vLLM, llama.cpp, ONNX or WebSocket exports share Python outputs.

## Source and Validation

Contracts: [CAMPPlus](../funasr/models/campplus/model.py),
[ERes2NetV2](../funasr/models/eres2net/model.py),
[SenseVoice](../funasr/models/sense_voice/model.py),
[postprocessing](../funasr/utils/postprocess_utils.py),
[AutoModel](../funasr/auto/auto_model.py), and
[HTTP adaptation](../funasr/bin/_server_app.py).
The [guide tests](../tests/test_speaker_emotion_docs.py) execute the published
program with recording SDK doubles and the real presentation helper. They check
field preservation, serialization and invalid input handling, not acoustic
quality, identity matching, demographic performance or emotion accuracy.
