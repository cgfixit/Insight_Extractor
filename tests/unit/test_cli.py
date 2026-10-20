"""CLI output safety: encodable console output, outputs written first, atomic state."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import insight_extractor.__main__ as cli
from insight_extractor.extractor import InsightExtractor, _markdown_text


class FakeModel:
    def encode(self, texts: str | list[str], *_args: Any, **_kwargs: Any) -> Any:
        items = [texts] if isinstance(texts, str) else list(texts)
        return np.array([[float(i), 1.0, 0.5, 0.25] for i, _ in enumerate(items, 1)])


class FakeTokenizer:
    def tokenize_sentences(self, text: str, *, max_tokens: int = 512) -> list[str]:
        del max_tokens
        return [part.strip() for part in text.split(".") if len(part.strip()) > 10]


class FakeExtractor(InsightExtractor):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._model = FakeModel()
        self._tokenizer = FakeTokenizer()


TEXT = (
    "SafeClaw \u2192 PsyClaw ransomware exploited CVE-2026-1234 on the gateway.\n"
    "\u2502 \u2605 The CO\u2082 telemetry \x1b]0;owned\x07\x1b[2J was spoofed by the operator.\n"
)


def test_cli_survives_strict_cp1252_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "report.md"
    source.write_text(TEXT, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "InsightExtractor", FakeExtractor)
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252", errors="strict"))

    status = cli.main([str(source)])
    sys.stdout.flush()

    assert status == 0
    assert (tmp_path / "insights_extracted.md").exists()
    assert (tmp_path / "insight_extractor_state.json").exists()
    console = raw.getvalue().decode("cp1252")
    assert "Results saved to: insights_extracted.md" in console
    assert "\\u2192" in console
    assert "\x1b" not in console and "\\x1b]0;owned\\x07" in console


def test_cli_reports_write_failure_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    source = tmp_path / "report.txt"
    source.write_text("Ransomware operators exploited the VPN gateway.", encoding="utf-8")
    (tmp_path / "insights_extracted.md").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "InsightExtractor", FakeExtractor)

    assert cli.main([str(source)]) == 1
    captured = capsys.readouterr()
    assert "error: failed to write output" in captured.err
    assert "Traceback" not in captured.err


def test_save_state_failure_keeps_previous_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    state = tmp_path / "state.json"
    extractor.save_state(state)
    before = state.read_text(encoding="utf-8")
    extractor.thread_keywords.append("phishing")

    def fail_replace(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("insight_extractor.extractor.os.replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        extractor.save_state(state)

    assert state.read_text(encoding="utf-8") == before
    assert json.loads(before)["thread_keywords"] == ["ransomware"]
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_console_safe_escapes_control_characters() -> None:
    assert cli._console_safe("a\x1b[2Jb\n  c\x07") == "a\\x1b[2Jb c\\x07"


def test_markdown_escapes_tildes_in_short_paths() -> None:
    assert _markdown_text("C:\\PROGRA~1\\COMMON~1") == "C:\\\\PROGRA\\~1\\\\COMMON\\~1"
