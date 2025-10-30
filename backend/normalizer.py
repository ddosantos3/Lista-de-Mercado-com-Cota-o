from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class Normalizer:
    def __init__(self, mapping: Dict[str, str]) -> None:
        # mapping: variant(lower) -> canonical(lower)
        self.mapping = {k.lower(): v.lower() for k, v in mapping.items()}

    def normalize(self, term: str) -> str:
        t = term.strip().lower()
        if not t:
            return t
        return self.mapping.get(t, t)

    def add(self, variant: str, canonical: str) -> None:
        self.mapping[variant.strip().lower()] = canonical.strip().lower()


def load_default_mapping() -> Dict[str, str]:
    # Simple starting set of synonyms
    return {
        "arroz": "arroz 5kg tipo 1",
        "feijao": "feijão carioca 1kg",
        "feijão": "feijão carioca 1kg",
        "oleo": "óleo de soja 900ml",
        "óleo": "óleo de soja 900ml",
        "cafe": "café 500g",
        "café": "café 500g",
        "acucar": "açúcar 1kg",
        "açucar": "açúcar 1kg",
        "açúcar": "açúcar 1kg",
        "trigo": "farinha de trigo 1kg",
        "leite": "leite longa vida 1l",
    }


def load_mapping_from_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_mapping_to_file(path: Path, mapping: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

