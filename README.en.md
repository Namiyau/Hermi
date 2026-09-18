# Hermi Gateway — Local AI Web/PWA Gateway

[简体中文](README.md) | English | [日本語](README.ja.md)

Hermi is a local gateway for a Web/PWA AI client. It handles users, sessions, profile routing, permissions, quotas, approvals, scheduled jobs, and the bridge to QLOS-Lite.

## Features

* Owner and friend authentication.
* Conversation and profile routing for Hermes.
* Permission, quota, approval, attachment, and scheduled-job APIs.
* Web/PWA static client with Chat and Professional views.
* Optional QQ bridge through QLOS-Lite.
* FRP example limited to the Hermi gateway port.

## Build and run

Install Python 3.11+, then install the dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn hermi_gateway.app:app --host 127.0.0.1 --port 8789
```

Open `http://127.0.0.1:8789` after starting an external Hermes Gateway.

## Configuration

Copy `secrets.local.env.example` to `secrets.local.env` and fill local values. Never commit the local file. Hermes profile gateways normally use ports `8642`, `8643`, and `8644`; QLOS-Lite normally uses `8766`.

## Dependencies

Required: Python, FastAPI, Uvicorn, HTTPX, Pydantic, and an external Hermes Gateway. QLOS-Lite and FRP/SakuraFRP are optional integrations.

## Security

Only expose Hermi through FRP. Keep Hermes, QLOS-Lite, and NapCatQQ on local interfaces. Do not share Owner tokens with remote users.

## License

No open-source license has been selected for this project yet.
