from pathlib import Path


def test_all_stack_starts_trainee_and_stops_both_gateway_command_styles():
    script = (Path(__file__).parents[1] / "scripts" / "start_hermi_all.ps1").read_text(
        encoding="utf-8"
    )

    assert '@($HermesExe, "-p", "trainee", "gateway")' in script
    assert '*hermes_cli.main*gateway*' in script
    assert '*hermes.exe* gateway*' in script
