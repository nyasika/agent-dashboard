"""Tétel betöltő és súlyozott véletlenhúzó logika."""

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "tetelek"


def load_all() -> dict[int, dict]:
    """Betölti az összes feldolgozott tételt. Visszatér: {id: tetel_dict}"""
    tetelek = {}
    for path in sorted(DATA_DIR.glob("tetel_*.json")):
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
        tetelek[t["id"]] = t
    return tetelek


def load_one(tetel_id: int) -> dict | None:
    path = DATA_DIR / f"tetel_{tetel_id:02d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pick_weighted(confidence_map: dict[int, int], all_ids: list[int]) -> int:
    """Súlyozott véletlenhúzás confidence alapján.

    confidence_map: {tetel_id: weight} ahol weight 1-4
      1 = Magabiztosan (legkisebb valószínűség)
      4 = Nem tudtam   (legnagyobb valószínűség)
    Tételek amelyek még nem lettek értékelve: weight=3 (alapértelmezett)
    """
    weights = [confidence_map.get(tid, 3) for tid in all_ids]
    return random.choices(all_ids, weights=weights, k=1)[0]


def tetel_list_summary(tetelek: dict[int, dict], confidence_map: dict[int, int]) -> list[dict]:
    """Visszaad egy listát az összes tétel állapotával a sidebar-hoz."""
    CONFIDENCE_LABELS = {1: "Magabiztos", 2: "Jól ment", 3: "Bizonytalan", 4: "Nem tudtam"}
    result = []
    for tid in sorted(tetelek.keys()):
        t = tetelek[tid]
        w = confidence_map.get(tid)
        result.append({
            "id": tid,
            "cim": t["cim"],
            "confidence": w,
            "confidence_label": CONFIDENCE_LABELS.get(w, "Nem gyakorolt"),
        })
    return result
