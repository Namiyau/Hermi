# Hermi FRP 接入

本阶段只允许外部浏览器访问 Hermi Web/API：

```text
外部浏览器 -> frps/SakuraFRP -> frpc -> 127.0.0.1:8789
```

禁止映射 NapCat `3000`、Hermes `8642/8643/8644`、QLOS `8766`。远程用户使用 Friend token，不得共享 Owner token。

## 使用步骤

1. 安装官方 `frpc`，或在 SakuraFRP 控制台创建指向本机 `127.0.0.1:8789` 的 TCP/HTTPS 隧道。
2. 复制 `frpc.hermi.example.toml` 为 `frpc.hermi.local.toml`。
3. 填写 `serverAddr`、`serverPort`、`auth.token` 和服务端分配的 `remotePort`。
4. 运行 `scripts\test_hermi_frp_config.ps1` 做离线安全检查。
5. 设置 `HERMI_FRPC_PATH`，或把 `frpc.exe` 放到 PATH。
6. 双击 `Start_Hermi_FRP.bat`。停止使用 `Stop_Hermi_FRP.bat`。

公网应优先使用 HTTPS/WSS。FRP 只负责隧道，Hermi 仍通过 Friend token 做应用层认证。不要把 `frpc.hermi.local.toml` 提交或发给别人。

SakuraFRP 自带启动器时，可以不使用本目录启动脚本，但节点目标必须保持 `127.0.0.1:8789`，且不得勾选其他本机服务端口。
