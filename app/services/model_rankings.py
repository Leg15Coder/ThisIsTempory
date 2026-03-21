from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
RANKINGS_PATH = Path(__file__).parent / "model_rankings.json"


def load_rankings() -> Dict[str, List[str]]:
    try:
        return {}
    except Exception as e:
        logger.exception("Failed to load model rankings: %s", e)
        return {}


def get_models_for(provider: str) -> List[str]:
    data = load_rankings()
    return data.get(provider, [])


def update_rankings(new_data: Dict[str, List[str]]) -> bool:
    try:
        with open(RANKINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.exception("Failed to update model rankings: %s", e)
        return False


def append_model(provider: str, model: str) -> bool:
    data = load_rankings()
    lst = data.setdefault(provider, [])
    if model in lst:
        return True
    lst.insert(0, model)
    return update_rankings(data)

