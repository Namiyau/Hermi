# Hermi Gateway

简体中文 | [English](README.en.md) | [日本語](README.ja.md)

Hermi 是本地 AI 集合体的 Web/PWA 网关，负责用户登录、会话、角色/profile 路由、权限、额度、审批、定时任务和与 QLOS-Lite 的桥接。

## 依赖关系

- 必需：Hermes Gateway，默认使用本机 `8642` 等 profile API。
- 可选：QLOS-Lite，用于 QQ 消息收发和 QQ 上下文。
- 可选：外部 FRP/SakuraFRP，只把 Hermi 网关映射给远程浏览器；本仓库只保留自己的配置示例。
- 可选：外部 Open WebUI，可通过兼容 API 与本地服务协作；Open WebUI 本身不在本仓库。

## 本地运行

1. 安装 Python 3.11+、FastAPI、Uvicorn、HTTPX、Pydantic。
2. 复制 `secrets.local.env.example` 为 `secrets.local.env`，填写本机配置；不要提交后者。
3. 启动 Hermes profile gateway。
4. 运行：

```powershell
python -m uvicorn hermi_gateway.app:app --host 127.0.0.1 --port 8789
```

浏览器打开 `http://127.0.0.1:8789`。

## 测试

```powershell
python -m pytest -q
```

测试会覆盖网关核心 API、鉴权、权限、QQ 桥接、定时任务、附件安全、FRP 配置检查和前端静态结构。测试时会使用临时目录，不应把真实运行时数据复制进仓库。

## 安全

Hermi 网关可以被 FRP 暴露，但 Hermes `8642/8643/8644`、QLOS-Lite `8766` 和 NapCat `3000` 应保持本机可见。远程用户只使用 Friend token，不能共享 Owner token。

## 当前职责

本目录只包含 Hermi 源码、Web 静态资源、测试和不含密钥的 FRP 示例。profile、模型、记忆、会话、数据库和媒体属于本地运行时，不在这里发布。
