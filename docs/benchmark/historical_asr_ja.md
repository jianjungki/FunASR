# ASR ベンチマークの過去の記録

[English](historical_asr.md) | [中文](historical_asr_zh.md) | [한국어](historical_asr_ko.md)

このページは、以前の FunASR 比較を参照する読者のために、**出典情報が不完全な過去の記録**を保存したものです。
新しい測定、汎用ランキング、現在の checkpoint・機器・デプロイに対する保証ではありません。
対象データは**中国語の音声**であり、この日本語ページは日本語や韓国語の認識精度を測ったものではありません。
新しい評価を行う場合は[性能測定の方法（英語）](rtf_reproducibility.md)から始めてください。

## 過去の概要

下表は元の日本語ページの表現と数値を保持しています。
「最高」などの表現はその報告の範囲だけを指し、すべてのモデルやハードウェアには適用できません。

| 指標 | 結果 |
| --- | --- |
| データセット | 中国語の長時間音声 184 ファイル、合計 11,539 秒、192.3 分。 |
| GPU | NVIDIA H100 80GB HBM3. |
| 最高 GPU 速度 | SenseVoice-Small: 169.6x realtime in the full benchmark, 211.8x in the initial run. |
| 最高 CPU 速度 | SenseVoice-Small: 17.2x realtime; Paraformer-Large: 15.6x realtime. |
| ベースライン | OpenAI Whisper-large-v3: 13.4x realtime on GPU. |

**全体実行の 169.6x と初回実行の 211.8x は、別々に報告された結果**です。
元のページは測定日を明記していません。**2026-09-07 は出典スナップショットを確認した日であり、測定日ではありません**。

## 過去の結果

この表のすべての数値とメモは元の報告の歴史的な記述であり、**現在の API の機能保証ではありません**。
モデルが生のタグを出力することは、HTTP エンドポイントがそのタグを返すことを意味しません。
過去のタイムスタンプに関する記述も、現在の[モデル選択ガイド](../model_selection_ja.md)に代わるものではありません。

| モデル | デバイス | RTF | 速度 | CER | メモ |
| --- | --- | --- | --- | --- | --- |
| SenseVoice-Small | GPU | 0.005896 | 169.6x | 7.81% | ASR + language / emotion / event tags; CER after tag stripping. |
| Paraformer-Large | GPU | 0.008359 | 119.6x | 10.18% | Fast non-autoregressive Chinese ASR with VAD/punctuation pipeline. |
| Fun-ASR-Nano | GPU | 0.058803 | 17.0x | 8.06% | 中国語・英語・日本語、7つの中国語方言グループ、26の地域アクセントに対応する LLM-based ASR。hotword に対応。信頼できる checkpoint-native timestamp は未対応（[#106](https://github.com/QwenAudio/Fun-ASR/issues/106)）。 |
| GLM-ASR-Nano | GPU | 0.026974 | 37.1x | 31.07% | LLM-based multilingual ASR. |
| Whisper-large-v3-turbo (OpenAI) | GPU | 0.021708 | 46.1x | 21.71% | OpenAI Whisper implementation. |
| Whisper-large-v3 (OpenAI) | GPU | 0.074694 | 13.4x | 20.02% | ベースライン for large Whisper quality. |
| SenseVoice-Small | CPU | 0.057988 | 17.2x | 7.81% | CPU run from the remaining benchmark script. |
| Paraformer-Large | CPU | 0.064056 | 15.6x | 10.18% | CPU viable for batch jobs. |
| Fun-ASR-Nano | CPU | 0.274318 | 3.6x | 8.06% | LLM-based model is heavier but still above realtime. |

CPU/GPU の行で同じ CER が繰り返されていても、それぞれを独立に採点した証拠にはなりません。
確認した資料には、生の予測、参照テキスト、採点プログラムがありません。
「タグを除去してから CER を計算」という記述は過去の主張として保存しており、今回検証した採点結果ではありません。
数値の桁数や丸められた速度・RTF の組は、再計算せずに保持しています。

## 出典と制約

[元の日本語 HTML](https://github.com/modelscope/FunASR/blob/67d63b80a246dc33749e43904c294e0409cd9183/ja/benchmark.html)は
過去の GitHub Pages のコミットに固定されています。出典確認時に、このファイルは保存済みの公開ページの
スナップショットとバイト単位で一致しました。これは表の出典を示すものであり、
測定の正しさや再現可能性を証明するものではありません。

元の報告では RTF を総推論時間と総音声時間の比、速度をその逆数としています。
速度は RTFx とも呼ばれます。

```text
RTF  = total inference time / total audio duration
RTFx = total audio duration / total inference time = 1 / RTF
```

次のコマンドは**過去の記録であり、確認したチェックアウトからそのまま実行することはできません**。
確認した FunASR ソースのリビジョン `386f6f9106684ba5a114e796147db4396a09eab5` には、
参照先の三つのファイルがありません。本ページは代替スクリプトや再現用データを提供しません。

```text
python benchmark/run_full_benchmark.py
python benchmark/run_remaining.py
python benchmark/fix_sensevoice_cer.py
```

元の報告では CPU の型番・スレッド数、データの構成と参照テキストの一覧、正確な checkpoint のリビジョン、
ソフトウェア・ドライバーのバージョン、ファイルごとの予測や計時ログが明らかではありません。
ウォームアップ、I/O、前処理を含むかなど、計時範囲も十分には記録されていません。
これらがないため、この表を直接再現することはできず、CPU と GPU の比較をあらゆる本番環境に一般化できません。

この記録の **11,539 秒**と、[vLLM の測定方法（英語）](rtf_reproducibility.md)に記載された
**11,541 秒**は別々に引用してください。両方が 184 ファイルと述べていても、同じファイル群であるとは限りません。
二つの表を統合したり、2 秒の差を勝手に補正したりしないでください。

## 現在の選び方

以下は**元の推奨表を過去の文脈として保存したもの**です。
新たに検証した推奨や性能ランキングではありません。

| 用途 | 推奨モデル |
| --- | --- |
| 最速の本番書き起こし | SenseVoice-Small または Paraformer-Large。 |
| CPU バッチ書き起こし | まず SenseVoice-Small。中国語の本番 pipeline では Paraformer-Large。 |
| 中国語・英語・日本語、および中国語の方言/アクセントを扱う LLM-style 認識 | Fun-ASR-Nano。31言語が必要な場合は別 checkpoint の [Fun-ASR-MLT-Nano](https://huggingface.co/FunAudioLLM/Fun-ASR-MLT-Nano-2512) を使用し、LLM decode throughput を高める場合は [vLLM](../vllm_guide.md) を使用。 |
| OpenAI 互換ローカル endpoint | [funasr-server](../agent_integration_ja.md) を使い、model alias は `sensevoice`、`paraformer`、または `fun-asr-nano`。 |

現在の判断には、[モデル選択](../model_selection_ja.md)、[Agent のインターフェースと制約](../agent_integration_ja.md)、
[デプロイ方式](../deployment_matrix_ja.md)、[vLLM ガイド（英語）](../vllm_guide.md)を使ってください。
別 checkpoint である MLT-Nano の 31 言語対応を、基本 Fun-ASR-Nano の対応範囲と混同しないでください。
対象言語、手元の音声、実行環境、エンドツーエンドの遅延を評価してから方式を選びます。
公式 native vLLM と split-engine は checkpoint と API が異なるため、相互に置き換えないでください。

新しい計測には[性能測定の方法（英語）](rtf_reproducibility.md)、同時接続を伴うリアルタイムサービスには
[WebSocket ベンチマーク（英語）](realtime_ws_benchmark.md)を参照してください。
現在の[移行用計時ツール](../../examples/migration/benchmark_funasr.py)は手元の音声で FunASR の時間を測るもので、
**CER/WER を計算せず、Whisper も実行せず、欠けている過去のスクリプトを再現しません**。
計時範囲、失敗したファイル、品質評価は分けて明示してください。
