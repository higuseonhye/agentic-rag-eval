from __future__ import annotations

import json
from typing import Any


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)

