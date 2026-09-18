from pathlib import Path


ROOT = Path(__file__).parents[1]
DESKTOP = Path.home() / "Desktop"


def test_all_start_includes_watchdog_and_self_elevates():
    launcher = (ROOT / "scripts" / "start_all_6.ps1").read_text(encoding="utf-8")
    desktop_bat = (DESKTOP / "ALL-start.bat").read_text(encoding="utf-8")

    assert "4_watchdog_loop.bat" in launcher
    assert "Watchdog" in launcher
    assert '"py.exe", "python.exe", "pythonw.exe"' in launcher
    assert "-Verb RunAs" in desktop_bat


def test_all_stop_stops_watchdog_and_self_elevates():
    stopper = (ROOT / "scripts" / "stop_all_6.ps1").read_text(encoding="utf-8")
    desktop_bat = (DESKTOP / "ALL-stop.bat").read_text(encoding="utf-8")

    assert "host_watchdog.py*watchdog-loop" in stopper
    assert "-Verb RunAs" in desktop_bat
