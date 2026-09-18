# Hermi Gateway — ローカル AI Web/PWA ゲートウェイ

[简体中文](README.md) | [English](README.en.md) | 日本語

Hermi はローカル Web/PWA AI クライアント用のゲートウェイです。ユーザー、セッション、profile ルーティング、権限、利用量、承認、定期タスク、QLOS-Lite 連携を扱います。

## 機能

* Owner と friend の認証。
* Hermes の会話と profile ルーティング。
* 権限、利用量、承認、添付ファイル、定期タスク API。
* Chat / Professional 表示を持つ Web/PWA クライアント。
* QLOS-Lite 経由の QQ 連携。
* Hermi ゲートウェイだけを公開する FRP 設定例。

## ビルドと実行

Python 3.11 以上を用意して、次を実行します。

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn hermi_gateway.app:app --host 127.0.0.1 --port 8789
```

外部 Hermes Gateway を起動してから `http://127.0.0.1:8789` を開きます。

## 設定

`secrets.local.env.example` を `secrets.local.env` にコピーして、ローカルの値を入力してください。実際の設定ファイルは Git に登録しないでください。Hermes profile は通常 `8642`、`8643`、`8644`、QLOS-Lite は `8766` を使用します。

## 依存関係

Python、FastAPI、Uvicorn、HTTPX、Pydantic、外部 Hermes Gateway が必要です。QLOS-Lite と FRP/SakuraFRP は任意の連携です。

## セキュリティ

FRP で公開するのは Hermi だけにしてください。Hermes、QLOS-Lite、NapCatQQ はローカル接続に限定し、Owner token をリモートユーザーと共有しないでください。

## ライセンス

このプロジェクトのオープンソースライセンスはまだ選択されていません。
