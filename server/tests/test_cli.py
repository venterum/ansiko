from __future__ import annotations

import argparse
import subprocess

from ansiko.cli import _install_systemd


def test_install_systemd_writes_unit(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('host = "127.0.0.1"\nport = 8765\ntoken = "secret"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("ansiko.cli.shutil.which", lambda name: "/opt/ansiko")
    calls = []

    def run(command, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("ansiko.cli.subprocess.run", run)
    args = argparse.Namespace(config=str(config), no_start=False)
    assert _install_systemd(args) == 0

    unit = tmp_path / "xdg" / "systemd" / "user" / "ansiko.service"
    text = unit.read_text()
    assert 'WorkingDirectory="' not in text
    assert "WorkingDirectory=" + str(tmp_path) in text
    assert 'ExecStart="/opt/ansiko" serve --config' in text
    assert calls[0] == ["systemctl", "--user", "daemon-reload"]
    assert calls[-1] == ["systemctl", "--user", "enable", "--now", "ansiko.service"]
