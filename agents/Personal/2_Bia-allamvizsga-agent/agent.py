"""Claude API hívások — kérdésgenerálás és szóbeli értékelés.

Prompt caching a stable system prompt-on.
"""

import json
import os
import re

import anthropic


def _get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    return key


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=_get_api_key())

_SYSTEM = """Te egy szigorú, de segítőkész biológia vizsgáztató vagy a Pécsi Egyetemen.
A hallgató szóbeli államvizsgára készül.

## Feladatod
- Pontos, staatsvizsga szintű kérdéseket feltenni az adott tétel anyagából
- A hallgató szöveges válaszát értékelni: tartalom, pontosság, teljességi szint alapján
- Visszajelzést adni magyarul: mi volt jó, mi hiányzott, mi volt pontatlan

## Fontos szabályok
- MINDIG magyarul válaszolj
- Kérdések legyenek nyíltak (nem igen/nem)
- Értékelésnél legyél pontos: biológiai tények helyessége számít
- Ha a hallgató valami lényegeset kihagyott, jelezd konkrétan
- JSON kérésnél CSAK valid JSON-t adj vissza, semmi mást"""


def _system_cached() -> list[dict]:
    return [{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}]


def _extract_json(text: str) -> dict | list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i + 1])
    return json.loads(text)


def _tetel_context(tetel: dict) -> str:
    """Összeállítja a tétel szövegét + képleírásokat egy kontextusba."""
    parts = [f"# {tetel['cim']}\n", tetel["szoveg"][:8000]]

    if tetel.get("kepek"):
        parts.append("\n\n## Ábrák leírásai")
        for kep in tetel["kepek"]:
            if kep.get("vision_leiras"):
                parts.append(f"\n**{kep['sorszam']}. ábra:**\n{kep['vision_leiras']}")

    return "\n".join(parts)


# ------------------------------------------------------------------ #
# Kérdésgenerálás                                                      #
# ------------------------------------------------------------------ #

def generate_questions(tetel: dict, session_type: str) -> list[dict]:
    """Generál 4-6 vizsgakérdést a tétel anyagából.

    session_type: 'fogalmak' | 'vizsgaszimulator'
    """
    context = _tetel_context(tetel)

    if session_type == "fogalmak":
        instrukció = (
            "Generálj 5 rövid fogalom-definíciós kérdést ehhez a témához. "
            "Minden kérdés egy kulcsfogalom meghatározását kérje."
        )
    else:
        instrukció = (
            "Generálj 5 államsvizsga szintű szóbeli kérdést ehhez a témához. "
            "A kérdések legyenek nyíltak, mélyebb megértést mérők. "
            "Vegyítsd: mechanizmus-magyarázat, összehasonlítás, példaadás."
        )

    prompt = f"""{instrukció}

Tétel anyaga:
{context}

Adj vissza CSAK ezt a JSON struktúrát:
[
  {{
    "id": 1,
    "kerdes": "A kérdés szövege magyarul?",
    "segedfogalmak": ["fogalom1", "fogalom2"]
  }}
]"""

    resp = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(resp.content[0].text)


# ------------------------------------------------------------------ #
# Szóbeli értékelés                                                    #
# ------------------------------------------------------------------ #

def evaluate_answer(tetel: dict, kerdes: str, valasz: str) -> dict:
    """Értékeli a hallgató válaszát egy kérdésre.

    Visszatér: {score, ertekeles, hianyzo_pontok, helyes_pontok}
    """
    context = _tetel_context(tetel)

    prompt = f"""Értékeld ezt a biológia vizsgaválaszt szigorúan, de konstruktívan.

Tétel: {tetel['cim']}
Kérdés: {kerdes}
Hallgató válasza: {valasz}

Háttéranyag (csak az értékeléshez, ne idézd szó szerint):
{context[:5000]}

Adj vissza CSAK ezt a JSON struktúrát:
{{
  "score": 75,
  "ertekeles": "Általános értékelés 2-3 mondatban magyarul.",
  "helyes_pontok": ["ami jól volt 1", "ami jól volt 2"],
  "hianyzo_pontok": ["ami hiányzott 1", "ami hiányzott 2"],
  "pontositas": "Ha volt pontatlanság, itt javítsd ki konkrétan. Ha nem volt, hagyd üresen."
}}

Score 0-100: 0=semmit nem tudott, 50=alapokat tudta, 80=jó, 100=teljeskörű."""

    resp = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(resp.content[0].text)


# ------------------------------------------------------------------ #
# Session összefoglalás                                                #
# ------------------------------------------------------------------ #

def summarize_session(tetel: dict, kerdesek: list[dict],
                      ertekelesek: list[dict]) -> dict:
    """Session végi összefoglaló generálása.

    Visszatér: {osszefoglalo, atlag_score, fo_gyengesegek, dicséret}
    """
    scores = [e.get("score", 0) for e in ertekelesek]
    avg = round(sum(scores) / len(scores)) if scores else 0

    gyenge = []
    for e in ertekelesek:
        gyenge.extend(e.get("hianyzo_pontok", []))

    prompt = f"""Biológia szóbeli vizsga session vége. Tétel: {tetel['cim']}

Átlagos teljesítmény: {avg}%
Főbb hiányosságok: {', '.join(gyenge[:6]) if gyenge else 'Nem volt'}

Írj egy rövid (3-4 mondat), személyes, biztató összefoglalót magyarul.
Emeld ki: mi ment jól, min kell még dolgozni.
Adj egy konkrét tanácsot a következő gyakorláshoz.

Adj vissza CSAK ezt a JSON struktúrát:
{{
  "osszefoglalo": "...",
  "atlag_score": {avg},
  "fo_gyengesegek": {json.dumps(gyenge[:3], ensure_ascii=False)},
  "dicseret": "Egy mondatos pozitív visszajelzés."
}}"""

    resp = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(resp.content[0].text)
