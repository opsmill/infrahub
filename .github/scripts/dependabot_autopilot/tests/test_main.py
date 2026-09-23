import pytest

from dependabot_autopilot.__main__ import SUBCOMMANDS, main


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_subcommand_exits_zero(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv=[command]) == 0
    assert capsys.readouterr().out == f"{command}: not implemented\n"


def test_unknown_subcommand_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv=["unknown"])
    assert exc_info.value.code == 2
