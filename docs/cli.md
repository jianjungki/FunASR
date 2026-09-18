# Command-Line Interface

[中文](cli_zh.md) | [Python SDK](python_api.md) | [Model selection](model_selection.md)

Use `funasr` to transcribe local audio files, write structured results, or produce
subtitles. This guide follows the parser and formatter in
[`funasr/cli.py`](../funasr/cli.py); it is not the HTTP server or the Hydra CLI.

## Basic Usage

Transcribe one file with the default `sensevoice` model, or select a CLI alias:

```bash
funasr audio.wav
funasr audio.wav --model paraformer
funasr audio.wav --device cpu
```

Choose the next task: [structured JSON](#json), [multiple files](#advanced-examples),
[subtitles](#srt), or [speakers and hotwords](#speakers-and-hotwords).
Inputs must be existing local files. Download remote audio yourself first; the
CLI does not accept an audio URL as its positional input.

## Installation

Install FunASR in your chosen Python environment, following the
[installation guide](installation/installation.md) for prerequisites and optional
model dependencies. These are usage commands, not a clean-install validation:

```bash
python -m pip install funasr
funasr --help
funasr --version
```

The selected models and VAD/punctuation/speaker components may download on first
use. They need working hub access or a populated cache, enough memory, and the
dependencies required by that checkpoint. `--hub ms` is the default; use `--hub hf`
to select Hugging Face. Device selection is `cuda:0` when PyTorch reports CUDA
available, otherwise `cpu`; use `--device` to override it. This availability check
does not guarantee enough GPU memory or a compatible model environment.

## Output Formats

### text (default)

Plain transcription text, one result per input file. Rich `<|...|>` model tags are
removed, so this is not an emotion/event-tag output interface.

```bash
funasr audio.wav -f text -o ./transcripts
```

Without `-o`, the CLI prints results to stdout. `--verbose` adds CLI loading and
timing messages to stderr; dependency/model logging may still appear on stdout.
Use output files for automation that needs isolated payloads.

### json

```bash
funasr audio.wav --timestamps -f json -o ./results
jq '.text' ./results/audio.json
```

This is an **illustrative formatter fixture**, not a measured transcription,
performance result, or promise that every model returns these optional fields:

```json
{
  "text": "Example.",
  "segments": [
    {"start": 0, "end": 1200, "text": "Example.", "timestamp": [[0, 1200]]}
  ],
  "timestamps": [[0, 1200]],
  "file": "audio.wav",
  "model": "sensevoice",
  "language": "auto",
  "audio_duration_s": 1.2,
  "processing_s": 0.01
}
```

| Field | Meaning |
|-------|---------|
| `text` | Cleaned transcription text. |
| `segments` | Included only when nonempty `sentence_info` produces segments. `start`/`end` are copied from the SDK (milliseconds for the sentence contract); text is cleaned. The per-segment `timestamp` can be null. |
| `timestamps` | Optional top-level model timestamp data retained with `--timestamps`. The CLI does not normalize it to a universal word schema. Pair arrays in this example are milliseconds; model-specific dictionary timestamp representations may use seconds. |
| `file` | Input basename, not its full path. |
| `model` | Selected CLI alias, not an immutable checkpoint revision. |
| `language` | Supplied hint or `auto` when omitted; not a detected-language result. |
| `audio_duration_s` | Audio metadata duration in seconds, rounded to three decimals; null if `soundfile.info` cannot read it. |
| `processing_s` | Per-file elapsed seconds around generation, rounded to three decimals. Excludes initial model loading and output formatting/writing; not end-to-end latency. |

`--timestamps` retains timestamps already returned by the model. It does **not**
request alignment or guarantee word-level timestamps. In JSON without this flag,
the top-level field is omitted, but nested segment timestamps can remain. Plain
text does not display timestamps. See [the SDK output contract](python_api.md)
for model-dependent results.

## Advanced Examples

### Multiple Files

```bash
funasr first.wav second.wav -f json -o ./results
funasr ./*.wav -f srt -o ./subs
```

One model instance is reused, and files are processed sequentially with
`batch_size=1`. The shell expands the glob; this is not parallel batch inference.
Outputs use each input's basename without its extension plus `.txt`, `.json`,
`.srt`, or `.tsv`. The output directory is created when needed. Files with the same
stem can overwrite each other, including results from previous runs.

Without `-o`, multiple JSON results are separate pretty-printed objects, **not** a
JSON array or JSONL stream. A missing file stops execution with exit code 1;
earlier output files remain. There is no resume or transactional batch option.

### srt

```bash
funasr audio.wav -f srt -o ./subs
funasr audio.wav -f srt --subtitle-segment-mode sentence -o ./raw-subs
```

SRT uses `HH:MM:SS,mmm` cue times. SRT and TSV request
`sentence_timestamp`, `output_timestamp`, and `return_time_stamps` from the SDK.
The default SenseVoice subtitle path also adds `ct-punc`; output still depends on
the model returning usable `sentence_info` and timing data.

The default `readable` mode groups eligible adjacent cues with a gap of at most
500 ms, a combined duration of at most 8 seconds, and at most 42 characters,
without crossing a known speaker change. Long cues are split only when their
available timestamps can support text alignment. These are grouping targets,
not a guarantee that every cue fits: unalignable or indivisible text can remain
over the limits. The CLI does not invent evenly spaced word timestamps.
`sentence` mode keeps raw model sentence boundaries. JSON and TSV are not grouped.

Without sentence segments, SRT falls back to one cue using available timestamp
bounds, then audio duration. If neither is available, the fallback can have zero
duration; inspect timing before publishing subtitles.

### tsv

```bash
funasr audio.wav -f tsv -o ./tables
```

TSV has `start`, `end`, and `text` columns, with start/end converted from sentence
milliseconds to seconds at three decimal places. Without segments, it emits one
text row with `0.000` start and end, not inferred alignment.

### Speakers and Hotwords

```bash
funasr meeting.wav --model paraformer --spk --timestamps -f json -o ./meetings
funasr audio.wav --model paraformer --language zh --hotwords "FunASR,达摩院"
funasr audio.wav --hub hf --model fun-asr-nano
```

`--spk` adds the `cam++` speaker model. JSON segments include `speaker` only when
the SDK supplies `spk` in `sentence_info`. It does not identify people by name or
guarantee diarization for every model. SRT grouping respects available speaker
boundaries, but the CLI's text/SRT/TSV formatters do not print speaker labels.

Hotwords are comma-separated, trimmed, and empty items discarded. The
`paraformer` alias forwards a space-joined `hotword` string; other aliases forward
a `hotwords` list. Recognition support depends on the model, not merely the
parser accepting the option. `--language` is also a model-specific hint: the
parser accepts any string and does not validate model language coverage.

## Limits

- This is a local-file SDK wrapper, not streaming, a network service, or native
  vLLM serving. See the [deployment matrix](deployment_matrix.md) for those paths.
- The four aliases below are the entire `--model` choice set. Arbitrary hub IDs,
  local model directories, and backend-selection flags are not supported here.
- `moss-transcribe-diarize` is **not** a CLI choice. Use the separate `AutoModel`
  adapter or `funasr-server` path in the [MOSS guide](moss_transcribe_diarize.md),
  with that guide's dependencies and limitations; do not pass it to `--model`.
- Model loading happens before the per-file existence check. Invalid input can
  therefore still incur loading/download time. Inference or dependency errors
  are not converted into a stable JSON error envelope.
- Timing, memory, language coverage, alignment, and speaker quality depend on
  checkpoint, hardware, environment, and audio. This guide makes no speed or
  production-capacity claim.

## Options

`audio` is one or more local file paths. `None` below is the actual parser default,
not a string to supply on the command line.

| Option | Short | Parser default | Meaning / choices |
|--------|-------|----------------|-------------------|
| `--model` | `-m` | `sensevoice` | `sensevoice`, `paraformer`, `paraformer-en`, `fun-asr-nano`. |
| `--hub` | `-H` | `ms` | `ms` (ModelScope) or `hf` (Hugging Face). |
| `--language` | `-l` | `None` | Omitted: no language argument is forwarded. Explicit hints such as `zh`, `en`, `ja`, `ko`, `yue`, `auto` depend on the model. |
| `--device` | | `None` | Automatically `cuda:0` if CUDA is available, otherwise `cpu`; explicit device string overrides this. |
| `--output-format` | `-f` | `text` | `text`, `json`, `srt`, `tsv`. |
| `--subtitle-segment-mode` | | `readable` | `readable` or `sentence`; affects SRT only. |
| `--output-dir` | `-o` | `None` | Omitted: stdout. Otherwise write per-file results to this directory. |
| `--timestamps` | | `False` | Retain available top-level timestamps; does not request alignment. |
| `--spk` | | `False` | Add speaker model; JSON speaker fields depend on SDK results. |
| `--hotwords` | | `None` | Comma-separated hints, forwarded according to the model alias. |
| `--verbose` | `-v` | `False` | CLI loading/timing messages to stderr. |
| `--version` | | Not applicable | Print installed FunASR package version and exit, not a model revision. |
| `--help` | `-h` | Not applicable | Print parser help and exit. |

## Models

| CLI alias | ASR model mapping | Scope |
|-----------|-------------------|-------|
| `sensevoice` | `iic/SenseVoiceSmall` | Chinese, English, Japanese, Korean, Cantonese; rich tags are stripped from CLI text. |
| `paraformer` | `paraformer-zh` | Chinese recognition with VAD and punctuation. |
| `paraformer-en` | `paraformer-en` | English recognition; the CLI also adds punctuation. |
| `fun-asr-nano` | `FunAudioLLM/Fun-ASR-Nano-2512` | Chinese, English, Japanese and Chinese dialects/accents; additional model dependencies apply. |

All four configurations include `fsmn-vad`; speaker and punctuation additions
follow the selected options described above. These mappings do not pin a hub
revision. The separate Fun-ASR-MLT-Nano checkpoint is not selected by the
`fun-asr-nano` alias. For other checkpoints use the [Python SDK](python_api.md)
and [model selection guide](model_selection.md).

## Legacy CLI

The original Hydra-based entry point remains `funasr-hydra`:

```bash
funasr-hydra ++model=paraformer-zh ++input=audio.wav
```

Its `++key=value` configuration is separate from the argparse flags documented
here; do not mix the two syntaxes.
