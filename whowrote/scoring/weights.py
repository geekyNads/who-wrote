"""Load weights.yaml once. The only place weights come from."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml

WEIGHTS: dict[str, Any] = yaml.safe_load(
    files("whowrote.scoring").joinpath("weights.yaml").read_text(encoding="utf-8")
)


def strength(signal_id: str) -> float:
    return float(WEIGHTS["signals"][signal_id])  # KeyError = forgot to add the weight
