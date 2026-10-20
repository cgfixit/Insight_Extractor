"""Lazy ML loading: the package and its light modules must import without torch."""

from __future__ import annotations

import subprocess
import sys

HEAVY_MODULES = {"torch", "transformers", "sentence_transformers", "sklearn"}

# Runs in a fresh interpreter: pytest's own process has usually imported the extractor
# (and therefore torch) via other test modules, so checking sys.modules here would be
# meaningless.
_PROBE = f"""
import sys
import insight_extractor
import insight_extractor.config
import insight_extractor.constants
import insight_extractor.models
import insight_extractor.exceptions
import insight_extractor.utils

loaded = {sorted(HEAVY_MODULES)!r}
leaked = sorted(set(loaded) & {{m.split(".")[0] for m in sys.modules}})
assert not leaked, f"light imports pulled in heavy ML modules: {{leaked}}"
"""


def test_light_modules_import_without_heavy_ml() -> None:
    """Importing the package and its light modules never loads torch/transformers."""
    subprocess.run([sys.executable, "-c", _PROBE], check=True)
