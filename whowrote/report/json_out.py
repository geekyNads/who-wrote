from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from whowrote.scoring.combine import Result


def to_json(result: Result, meta: dict[str, Any]) -> str:
    return json.dumps(
        {
            **meta,
            "estimated": None if result.inconclusive else result.top,
            "inconclusive": result.inconclusive,
            "probabilities": {k: round(v, 4) for k, v in result.probabilities.items()},
            "percents": result.percents,
            "signals": [asdict(s) for s in result.signals],
        },
        indent=2,
        ensure_ascii=False,
    )
