from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frp_scaffold_only_exposes_hermi_gateway():
    config = (ROOT / "frp" / "frpc.hermi.example.toml").read_text(encoding="utf-8")
    start = (ROOT / "scripts" / "start_hermi_frp.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "scripts" / "stop_hermi_frp.ps1").read_text(encoding="utf-8")
    check = (ROOT / "scripts" / "test_hermi_frp_config.ps1").read_text(encoding="utf-8")

    assert 'localIP = "127.0.0.1"' in config
    assert "localPort = 8789" in config
    assert "serverAddr = \"CHANGE_ME\"" in config
    assert "auth.token = \"CHANGE_ME\"" in config
    for forbidden in ("3000", "8642", "8643", "8644", "8766"):
        assert forbidden not in config
    assert "http://127.0.0.1:8789/health" in start
    assert "CHANGE_ME" in start
    assert "hermi_frp.pid" in start
    assert "hermi_frp.pid" in stop
    assert "Forbidden local port" in check
    assert (ROOT / "Start_Hermi_FRP.bat").exists()
    assert (ROOT / "Stop_Hermi_FRP.bat").exists()
