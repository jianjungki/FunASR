([English](README.md)|[简体中文](README_zh.md)|日本語|[한국어](README_ko.md))

# FunASR OpenAI 互換 API サーバー

FunASR OpenAI 互換 API は、音声ファイルを multipart HTTP で送る `/v1/audio/transcriptions` を提供します。これは音声転写用の OpenAI API の一部であり、API 全体、リアルタイム API、すべての SDK やフレームワーク機能への互換性を保証するものではありません。

本ページはリポジトリ内の[サンプルサービス](server.py)の手順です。パッケージ付属の `funasr-server` は[別の実装](../../funasr/bin/_server_app.py)であり、設定を流用する前に[API 契約](#api-contract)を確認してください。[日本語 Agent ガイド](../../docs/agent_integration_ja.md)はパッケージ付属サービスや各種連携の入口です。プロセス内で `AutoModel.generate()` を呼び出す場合は、Python SDK ガイドの[英語版](../../docs/python_api.md)または[中国語版](../../docs/python_api_zh.md)を参照してください。

**ローカル開発から始めてください。** このサービスには認証機能やアプリケーション側のアップロードサイズ上限が組み込まれておらず、SDK の仮の API キーも認証しません。下記ではホストの loopback に明示的にバインドします。共有・公開する前に、[セキュリティとゲートウェイガイド](SECURITY.md)に従い、TLS、認証、アップロードサイズ制限、レート制限、クライアントとゲートウェイのタイムアウトを設けてください。音声・転写文の保存期間とアクセス権を決め、`/health`、`/v1/models`、`/openapi.json` と Swagger UI `/docs` へのアクセスも制限します。CORS は認証の代わりにはなりません。

## API Contract

- **サンプル `server.py`**: 起動時のプリロードと、multipart `model` 省略時の既定値はどちらも `sensevoice` です。フォームは `file`、`model`、`language`、`response_format` を受け取ります。以下では `json` または `verbose_json` を使います。
- **パッケージ付属 `funasr-server`**: CLI の既定値 `--model auto` は、デバイス文字列が `cuda` で始まる場合に `fun-asr-nano`、それ以外では `sensevoice` を選びます。一方、multipart `model` を省略すると、プリロードとは独立して `fun-asr-nano` になります。

リクエストには毎回 `model` を明示し、稼働中の `/v1/models` と `/openapi.json` を確認してください。`paraformer-en` はサンプルサービスに登録されていますが、パッケージ付属サービスの組み込み別名ではありません。パッケージ付属サービスでカスタムモデルを使う場合は `--model-path` と適切な `--hub` を設定し、リクエストは `model="custom"` とします。これらの CLI オプションはサンプル `server.py` にはありません。任意の checkpoint ID を `--model` に渡せるという意味でもありません。

`response_format=verbose_json` は応答形式の選択であり、**話者分離やタイムスタンプ生成を有効にするスイッチではありません**。サンプルサービスはモデルが返した `sentence_info` のみを `segments` に変換し、なければ `segments=[]` を返します。SDK の `timestamps` や `ctc_timestamps` が存在しても、それらを直接 HTTP の `segments` として返す処理ではありません。Nano の CTC 時刻は必要な学習済み重みが揃っていることに依存し、HTTP 経由で常に取得できるわけではありません。

サンプルには `spk` フォームフィールドがありません。`spk=true` を送っても外部話者処理は有効になりません。パッケージ付属サービスでは `spk=true` により、ネイティブ話者分離モデル以外に対して別の話者処理を要求できます。既定値は `False` で、対応する依存環境とモデルが必要です。MOSS のネイティブ出力は録音内の匿名ラベルであり、実在する人物の識別や別録音間の同一人物判定ではありません。MOSS に外部 VAD や話者モデルを追加しないでください。

両サービスの `start` / `end` は秒単位です。SDK の `sentence_info` に含まれるミリ秒の座標は、HTTP アダプターで秒に変換されます。サンプルの `duration` は `generate()` の処理時間で、初回モデルロードを含まず、**音声の長さではありません**。サンプルの `language` は送信したヒント、未指定なら `auto` であり、言語検出結果とは限りません。パッケージ付属サービスの `duration` は音声の長さで、fallback 経路ではメタデータを読めない場合に 0 になることがあります。`language` は `auto` 以外の明示したヒントを優先し、それがなければ取得できた検出結果を使います。パッケージ付属サービスの fallback はテキストと音声の長さから粗い区間を合成する場合があり、単語単位の強制アラインメントではありません。

パッケージ付属の verbose 応答は `task` と区間ごとの `id` / `words` を含み、サンプルは `model` を含みます。話者フィールドは欠落または null の場合があります。共通の完全な JSON スキーマとは考えず、[応答例と話者リクエスト](CLIENTS.md#api-contract)を確認してください。`language` ヒントの意味もモデル依存です。SDK の `use_itn`、`hotwords`、キャッシュ、配列入力などはこの HTTP フォームのオプションではなく、`AutoModel.generate()` の全機能が公開されているわけではありません。

## クイックスタート

POSIX シェルと Python 3.11 を使い、新しいチェックアウトと仮想環境を作成します。PyPI パッケージのインストールだけでは、このリポジトリのサンプルファイルは配置されません。

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

固定するのはソースの revision です。依存パッケージ、モデル重み、音声デコーダー、CUDA 環境まで固定する手順ではありません。[インストールガイド](../../docs/installation/installation.md)に従って対象環境を準備してください。バージョン表示が `1.4.14` でも、公開済み PyPI パッケージと修正済みソースが同じ内容とは限りません。`pip check` は依存宣言の整合性を調べるもので、新規インストールや音声推論の成功を証明しません。

CUDA を利用する場合は対応する PyTorch、ドライバーなどを準備し、CPU サーバーを停止してから、同じ仮想環境と `examples/openai_api` ディレクトリで次の代替コマンドを実行します。同じポートで両方を同時起動しないでください。

```bash
python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000
```

モデルのロードを待ち、サーバー用ターミナルはそのままにします。初回ダウンロードや起動時間は checkpoint、キャッシュ、ネットワーク、ハードウェアに依存します。以下のクライアント操作は別のターミナルで行います。最初に `git clone` を実行した親ディレクトリから、同じ環境と作業ディレクトリに入ってください。

```bash
cd FunASR-api
source .venv/bin/activate
cd examples/openai_api
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models
curl -fsS http://localhost:8000/openapi.json
```

ヘルスチェックやモデル一覧の成功だけでは、音声転写の成功は確認できません。別途記載がない限り、以降のクライアントコマンドはこのディレクトリで実行します。

コピーして使える連携例が必要な場合は、[クライアントレシピ](CLIENTS.md)、[JavaScript/TypeScript レシピ](JAVASCRIPT.md)、[Gradio ブラウザデモ](GRADIO.md)、[ワークフローレシピ](WORKFLOWS.md)、[Postman コレクション](POSTMAN.md)、[OpenAPI 仕様](OPENAPI.md)、[セキュリティとゲートウェイガイド](SECURITY.md)、[Kubernetes デプロイテンプレート](kubernetes/README.md)を参照してください。

### エンドツーエンド smoke test

上記で準備したクライアント用ターミナルで、次のどちらかを実行できます。これは検証手順であり、対象環境での実行済み結果を示すものではありません。

```bash
bash smoke_test.sh
# curl/bash を使わないクロスプラットフォーム版:
python smoke_test.py
```

手動で確認する場合は、次の公開サンプルを利用できます。これは**中国語の音声**であり、このサンプルの転写は日本語や韓国語の精度検証ではありません。

```bash
curl -fL https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/BAC009S0764W0121.wav -o sample.wav
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@sample.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## Gradio ブラウザデモ

ローカルファイルのアップロードやマイクで録音した音声の送信には、保守されている [Gradio ブラウザデモ](GRADIO.md)を参照してください。この API サーバーとは別の Python 3.12 環境 `.venv-gradio` を使用します。ガイドでは `funasr`、`vllm`、`sglang-omni` の profiles、明示的なモデル選択、Docker/Kubernetes への接続、マイク権限、プライバシー上の制約を説明しています。UI は独立した HTTP クライアントであり、認証ゲートウェイでもリアルタイム文字起こしサービスでもありません。

## OpenAI SDK で使う

OpenAI の HTTP クライアントを別途インストールします。これは FunASR のプロセス内 Python SDK ではありません。

```bash
python -m pip install openai
```

`meeting.wav` を実際のローカル音声ファイルに置き換えて実行します。デコード可能な形式は準備した音声依存環境にも依存します。仮の `api_key` は SDK の必須引数を満たすための値で、サンプルサービスによる認証ではありません。

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

区間配列は空でも構いません。区間が返っても、そのことだけで正確な字幕時刻や話者分離が確認できるわけではありません。[API 契約](#api-contract)を参照してください。

## curl で使う

`audio.wav` は実際のローカル音声ファイルに置き換えてください。JSON に配列や URL を入れるのではなく、`file` にバイナリファイルを multipart で送ります。

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice

curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## 利用できるモデル

以下はサンプル `server.py` の `MODEL_CONFIGS` にある 5 つの別名です。SDK 全体やすべてのサーバーの共通モデル一覧ではなく、一定の処理速度や同時実行数を保証する表でもありません。

- `sensevoice`: SenseVoiceSmall + FSMN-VAD。既定では文単位のタイムスタンプや外部話者クラスタリングを有効にしません。
- `paraformer`: `paraformer-zh` + FSMN-VAD + CT 句読点モデル。句読点処理は設定されていますが、`verbose_json` だけでは文単位の記録を要求しません。
- `paraformer-en`: `paraformer-en` + FSMN-VAD。このサンプルには句読点モデルの設定がなく、パッケージ付属サービスの組み込み別名でもありません。
- `fun-asr-nano`: HF の Fun-ASR-Nano を `AutoModel` + FSMN-VAD で使用します。このサンプルは vLLM 経路ではなく、CTC 時刻が HTTP 区間として返る保証もありません。
- `moss-transcribe-diarize`: 第三者 OpenMOSS のネイティブ転写・話者分離アダプター。専用の依存環境が必要で、モデルが返した時刻と匿名話者ラベルを保持します。

SenseVoice の HTTP テキストからは `<|...|>` のリッチタグが除去されます。感情・イベントの専用フィールドを返す API ではありません。生のモデル出力が必要な場合はモデル別の Python SDK 契約を確認してください。

基本の Fun-ASR-Nano は中国語・英語・日本語と中国語方言・地域アクセントを対象とする経路であり、韓国語対応を含むという意味ではありません。31 言語の **Fun-ASR-MLT-Nano は別の checkpoint**で、この 2 つのサービスの組み込み別名ではありません。対象言語とモデル重みのライセンスは[モデル選択ガイド](../../docs/model_selection_ja.md)と個別のモデルカードで確認してください。FunASR ソフトウェアの MIT ライセンスは、すべてのモデル重みのライセンスを意味しません。

MOSS は固定 revision の third-party HF model を使用し、外部 VAD / speaker model とは併用しません。ラベルは録音内の匿名話者を示すもので、人物の身元を検証するものではありません。[MOSS deployment guide](../../docs/moss_transcribe_diarize.md) に `funasr-server`、Docker、Kubernetes、vLLM、SGLang Omni、LocalAI、FunClip の個別経路をまとめています。別名が一覧に存在するだけでは、全モデルのロード済み状態や依存環境の互換性は確認できません。

## API エンドポイント

| Endpoint | Method | 説明 |
|---|---|---|
| `/v1/audio/transcriptions` | POST | OpenAI 互換の音声文字起こし |
| `/v1/models` | GET | モデルエイリアスの一覧 |
| `/health` | GET | ヘルスチェック、ロード済みモデル、利用可能モデル |
| `/docs` | GET | FastAPI Swagger ドキュメント |
| `/openapi.json` | GET | 稼働中のサービスのスキーマ |

コードを書かずに確認したい場合は、[Gradio ブラウザデモ](GRADIO.md)でローカルアップロードやマイク入力を試すか、[Postman コレクション](POSTMAN.md)をインポートしてください。[OpenAPI 仕様](OPENAPI.md)はサンプル用の資料であり、パッケージ付属サービスの全フィールドを表すものではありません。API ゲートウェイやクライアント生成には稼働中のスキーマも確認してください。

## エージェントとローコードワークフロー

**LangChain**、**LlamaIndex**、**AutoGen**、**CrewAI**、**Semantic Kernel**、**Dify**、**n8n** などには、multipart HTTP またはツール関数を介して接続できます。利用するバージョンと本サービスのフィールドで個別に確認してください。全フレームワーク機能やリアルタイム API の互換性を保証するものではありません。

両サービスは、n8n 向けの特別なリクエスト別名 `whisper-1` を、起動時に選択したモデルへ対応付けます。これは OpenAI Whisper を実行する指定ではありません。パッケージ付属サービスで `--model-path` を指定している場合は `custom` に対応します。通常の HTTP ノードでは `model` を明示し、この互換別名を任意のモデル切替機構として扱わないでください。

Dify/n8n のファイルは multipart のバイナリ `file` として渡します。コンテナ内の `localhost` はそのコンテナ自身です。認可されたサービス名や到達可能なホストを設定し、接続問題の回避策として無認証の公開サービスにしないでください。URL を取得する worker を使う場合は、取得先の検証やサイズ制限も別途必要です。

- SDK、JavaScript/TypeScript、Agent tool の書き方は [クライアントレシピ](CLIENTS.md) と [JavaScript/TypeScript レシピ](JAVASCRIPT.md)を参照してください。
- Dify、n8n、HTTP ノード、webhook worker は [ワークフローレシピ](WORKFLOWS.md)を参照してください。
- GUI smoke test は [Postman コレクション](POSTMAN.md)を参照してください。
- schema-driven import には [OpenAPI 仕様](OPENAPI.md)を使えます。

## Docker デプロイ

リポジトリのルートから次のコマンドを実行します。すでにホスト側のサーバーを起動している場合は停止し、ポートを空けてください。既定のイメージはサンプル `server.py` を CPU モードで起動し、パッケージ付属の `funasr-server` は起動しません。

Dockerfile はバージョン未固定の PyPI FunASR と依存パッケージをインストールして、チェックアウトの `server.py` をコピーします。上のソース固定・editable install と同じ環境ではなく、再現可能なモデル検証済みイメージとも限りません。

```bash
cd examples/openai_api
cp .env.example .env

FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build
```

この POSIX シェルのプレフィックスは、既存 Compose ファイルのホスト側公開ポートを loopback に限定します。コンテナ内部のリスナーは `0.0.0.0` のままにしてください。コンテナのリスナーを `127.0.0.1` に変更することとは異なります。ホスト側 loopback はローカル開発用の設定であり、認証やネットワーク全体の安全性を保証するものではありません。

Compose と同時に起動しない場合の `docker run`:

```bash
docker build -t funasr-api .

docker run --rm -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cpu \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

GPU ホストでは NVIDIA Container Toolkit と CUDA 対応の PyTorch/FunASR イメージが必要です。CUDA 依存関係に合わせてイメージを調整した後、次のように起動できます。

```bash
docker run --rm --gpus all -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cuda \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

コンテナ起動後、同じ環境とサンプルディレクトリを用意した別のターミナルで、いずれかの方法で確認できます:

```bash
BASE_URL=http://localhost:8000 bash smoke_test.sh
python smoke_test.py --base-url http://localhost:8000
```

追加の build/run/smoke 手順は [validate_docker.sh](validate_docker.sh) にありますが、**既定ではホストの全インターフェースにポートを公開**し、上記の loopback 設定を引き継ぎません。実行前にネットワーク設定を確認し、共有ネットワークでのローカル検証には上記の明示的な loopback 手順を使ってください。GPU モードには CUDA 対応イメージと NVIDIA Container Toolkit が必要です。このページの記述は Docker や音声推論の実行済み検証結果ではありません。

## Kubernetes デプロイ

チーム内で共有したりゲートウェイ経由で公開したりする前に、[セキュリティとゲートウェイガイド](SECURITY.md)を確認し、TLS、認証、アップロード制限、レート制限、タイムアウト、ログと保存期間の方針を整えてください。

永続化されたモデルキャッシュ、ヘルスプローブ、プライベート `ClusterIP` を持つ内部クラスタサービスが必要な場合は、[Kubernetes デプロイテンプレート](kubernetes/README.md)から始めてください。サンプルイメージをビルドして push し、manifests を適用した後、`kubectl port-forward` と `python smoke_test.py --base-url http://localhost:8000` で検証します。

CUDA 対応イメージと GPU スケジューリング設定が整うまでは、デフォルトの CPU モードを維持してください。

## 設定

以下はサンプル `server.py` の既定値であり、`funasr-server` の既定値ではありません。[API 契約](#api-contract)と比較してください。ローカル手順では安全のため `--host 127.0.0.1` と `--device cpu` を明示しています。

| 引数 | デフォルト | 説明 |
|---|---|---|
| `--host` | `0.0.0.0` | バインドアドレス |
| `--port` | `8000` | ポート |
| `--device` | `cuda` | `cuda`、`cpu`、`mps` |
| `--model` | `sensevoice` | 起動時にプリロードするモデル |

Docker 環境変数:

| Env | デフォルト | 説明 |
|---|---|---|
| `FUNASR_PORT` | `8000` | `server.py` に渡すコンテナポート |
| `FUNASR_DEVICE` | `cpu` | コンテナのデバイスモード。CUDA 対応依存関係を持つイメージでのみ `cuda` に設定してください |
| `FUNASR_MODEL` | `sensevoice` | コンテナ起動時にロードするモデルエイリアス |
| `FUNASR_HOST_PORT` | `8000` | Compose のホスト側ポート指定。上のローカル手順では `127.0.0.1:8000` を指定します。 |

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| CUDA が利用できない | まず `--device cpu` で smoke test を通します。 |
| 8000 ポートが使用中 | `--port 9000` に変更し、`BASE_URL=http://localhost:9000 bash smoke_test.sh` または `python smoke_test.py --base-url http://localhost:9000` を実行します。 |
| モデルのダウンロードが遅い | 安定したネットワークで再試行するか、ModelScope/Hugging Face から事前にモデルをダウンロードします。 |
| Dify/n8n コンテナから `localhost` に接続できない | 認可された到達先のホスト名、Compose service name、または Kubernetes service name を使い、アクセス制御を維持します。 |
| 応答に `segments` がない | `response_format=verbose_json` で区間フィールドのある形式を選べますが、配列は空の場合があります。タイムスタンプや話者分離を有効にする指定ではありません。[API 契約](#api-contract)を確認してください。 |
