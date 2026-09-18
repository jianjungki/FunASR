# FunASR Subtitle Generator

Generate SRT/VTT subtitles from audio/video files.

## Usage

```bash
# Basic (auto-detect language)
python generate_subtitle.py video.mp4

# With speaker labels
python generate_subtitle.py meeting.wav --spk

# VTT format
python generate_subtitle.py podcast.mp3 --format vtt

# Use specific model
python generate_subtitle.py audio.wav --model paraformer-zh

# CPU mode
python generate_subtitle.py audio.wav --device cpu

# Preserve raw model sentence boundaries
python generate_subtitle.py audio.wav --segment-mode sentence

# Use shorter VAD segments when memory is limited
python generate_subtitle.py audio.wav --max-single-segment-time 30000
```

## Output Example (SRT)

```
1
00:00:00,420 --> 00:00:03,800
[Speaker 0] Let's discuss the Q3 plan.

2
00:00:04,200 --> 00:00:07,100
[Speaker 1] Sounds good. I have three points.
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | srt | Output format: srt or vtt |
| `--segment-mode` | readable | Cue grouping: readable or raw sentence boundaries |
| `--model` | SenseVoiceSmall | ASR model |
| `--device` | cuda | Device: cuda or cpu |
| `--max-single-segment-time` | 60000 | Maximum VAD segment length in milliseconds; reduce it when memory is limited |
| `--spk` | off | Add speaker labels |
| `--lang` | auto | Language hint |
| `-o` | input.srt | Output path |

Readable mode joins only adjacent short or continuation cues within bounded
gap, duration, length, and speaker limits. It does not rewrite recognized text
or punctuation.

The default 60-second VAD limit gives subtitle generation more context at
speech boundaries. For memory-constrained machines, lower it explicitly (for
example, `--max-single-segment-time 30000`).

## Install

```bash
pip install funasr
```
