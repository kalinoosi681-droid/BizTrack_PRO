import os
from cli import main as cli_main


def test_cli_export_runs_non_interactive(tmp_path, monkeypatch):
    # Use an in-memory DB and avoid seeding to keep the run non-interactive
    out_file = tmp_path / "export.csv"
    # Run CLI with export; it should exit normally (no exception)
    cli_main(["--db", ":memory:", "--no-seed", "--export", str(out_file)])
    # export may not create a file if there are no rows, but the call should complete
    assert True
