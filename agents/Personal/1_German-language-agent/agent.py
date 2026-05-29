"""Claude API wrapper for the German learning agent.

Uses claude-opus-4-7 with:
  - Prompt caching on the stable system prompt
  - Streaming for exercise generation
  - Adaptive thinking for assessment evaluation
"""

import json
import re
from typing import Optional

import anthropic

client = anthropic.Anthropic()

# ------------------------------------------------------------------ #
# Stable system prompt – cached on every call                         #
# ------------------------------------------------------------------ #

_SYSTEM = """Du bist ein einfühlsamer, geduldiger Deutschlehrer für Lernende auf B1-B2 Niveau.

Dein Schüler ist ein Ungar, der täglich 30 Minuten Deutsch übt. Er verwendet das Lehrbuch "Linie B1.2".

## Deine Kernaufgaben
1. Übungen generieren, die dem aktuellen Lernstand entsprechen
2. Fehler klar, konstruktiv und ermutigend korrigieren
3. Grammatikregeln auf Ungarisch erklären, wenn nötig
4. Abwechslungsreiche Übungen anbieten: Lückentext, Fehlerkorrektur, freies Schreiben, Grammatik-Drill

## Fokus-Grammatikthemen B1–B2
- Konjunktiv II (würde, wäre, hätte, könnte, sollte, müsste)
- Passiv (Präsens, Präteritum, Perfekt-Passiv)
- Relativsätze (alle Kasus, mit Präpositionen)
- Adjektivdeklination (bestimmter, unbestimmter Artikel, ohne Artikel)
- Trennbare und untrennbare Verben im Satz
- Wechselpräpositionen und feste Verbpräpositionen (an, auf, über + Akk./Dat.)
- Perfekt vs. Präteritum (wann welches verwenden)
- Nebensätze: kausal (weil/da), konzessiv (obwohl), final (damit/um…zu), temporal (als/wenn/nachdem)
- Indirekte Rede (Konjunktiv I)
- Nominalstil (B2, Schriftsprache)

## Wichtige Regeln
- Antworte IMMER auf Ungarisch, außer bei den deutschen Übungssätzen selbst
- Gib bei JSON-Anfragen AUSSCHLIESSLICH valides JSON zurück – kein Markdown, keine Erklärungen davor oder danach
- Sei ermutigend: B1→B2 ist ein großer, schaffbarer Schritt mit täglichem Üben
- Passe die Schwierigkeit dem aktuellen Fehlerstand an"""


def _system_cached() -> list[dict]:
    return [{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}]


def _extract_json(text: str) -> str:
    """Strip markdown fences and return the first JSON object or array."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Try to find the outermost JSON structure
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
                        return text[start: i + 1]
    return text


def _parse(text: str) -> dict | list:
    raw = _extract_json(text)
    return json.loads(raw)


# ------------------------------------------------------------------ #
# Assessment                                                           #
# ------------------------------------------------------------------ #

def generate_assessment() -> list[dict]:
    """Return 20 assessment questions covering B1-B2 grammar and vocabulary."""
    prompt = """Generálj egy 20 kérdéses B1-B2 szintfelmérő tesztet.

Összetétel:
- 4 kérdés: Konjunktiv II (fill_in és multiple_choice vegyesen)
- 3 kérdés: Passiv (fill_in)
- 3 kérdés: Relativsätze (fill_in)
- 2 kérdés: Adjektivdeklination (fill_in)
- 2 kérdés: Präpositionen (multiple_choice)
- 2 kérdés: Perfekt vs. Präteritum (multiple_choice)
- 4 kérdés: Szókincs B1-B2 (multiple_choice, 4 opció)

Minden kérdéshez pontosan ezt a JSON struktúrát add:
[
  {
    "id": 1,
    "type": "fill_in",
    "category": "Konjunktiv II",
    "question": "Wenn ich mehr Zeit ___ (haben), würde ich Deutsch lernen.",
    "context": "Ergänze die Lücke mit der richtigen Form.",
    "options": null,
    "correct_answer": "hätte"
  },
  {
    "id": 2,
    "type": "multiple_choice",
    "category": "Passiv",
    "question": "Das Haus ___ gerade renoviert.",
    "context": null,
    "options": ["wird", "ist", "hat", "war"],
    "correct_answer": "wird"
  }
]

Adj vissza CSAK a JSON tömböt, semmi mást."""

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == "text"), "[]")
    return _parse(text)


def evaluate_assessment(questions: list[dict], answers: dict[int, str]) -> dict:
    """Score assessment and return per-category results + recommendations."""
    pairs = []
    for i, q in enumerate(questions):
        pairs.append({
            "id": q["id"],
            "category": q["category"],
            "type": q["type"],
            "question": q["question"],
            "correct_answer": q.get("correct_answer", ""),
            "user_answer": answers.get(i, ""),
        })

    prompt = f"""Értékeld ezt a szintfelmérő tesztet. Vedd figyelembe, hogy kisebb helyesírási hibák vagy alternatív helyes formák elfogadhatók.

{json.dumps(pairs, ensure_ascii=False, indent=2)}

Adj vissza CSAK ezt a JSON struktúrát:
{{
  "grammar_score": 72,
  "vocabulary_score": 65,
  "writing_score": 70,
  "overall_level": "B1+",
  "category_scores": {{
    "Konjunktiv II": 50,
    "Passiv": 80,
    "Relativsätze": 60,
    "Adjektivdeklination": 70,
    "Präpositionen": 75,
    "Perfekt vs. Präteritum": 80
  }},
  "weaknesses": ["Konjunktiv II", "Relativsätze"],
  "strengths": ["Passiv", "Perfekt vs. Präteritum"],
  "summary": "Rövid, biztató összefoglalás magyarul (2-3 mondat)"
}}"""

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    return _parse(text)


# ------------------------------------------------------------------ #
# Practice sessions                                                    #
# ------------------------------------------------------------------ #

def generate_session(
    session_type: str,
    chapter: int,
    weaknesses: dict[str, dict],
    due_vocab: Optional[list[dict]] = None,
) -> dict:
    """Generate a practice session for the given type."""
    weak_cats = sorted(
        [(k, v) for k, v in weaknesses.items() if v.get("total", 0) > 0],
        key=lambda x: x[1]["wrong"] / max(x[1]["total"], 1),
        reverse=True,
    )
    top_weak = ", ".join(k for k, _ in weak_cats[:2]) or "általános B1-B2 témák"

    type_prompts = {
        "lueckentext": f"""Generálj 6 Lückentext feladatot.
Fókusz: {top_weak}.
A mondatok legyenek természetesek, 1-2 mondatosak.
Minden feladatnál jelöld a hiányzó szót ___ jellel a mondatban.""",

        "fehlerkorrektur": f"""Generálj 6 hibás mondatot, amiket javítani kell.
Fókusz: {top_weak}.
A hibák legyenek tipikus B1-B2 hibák (nem szókincs, hanem grammatika).
A correct_answer a TELJES JAVÍTOTT mondat legyen.""",

        "schreiben": f"""Generálj 3 fogalmazási feladatot.
Témák: Linie B1.2 {chapter}. fejezete.
Minden feladatnál kérj 3-5 mondatos választ.
A correct_answer egy minta-megoldás legyen.""",

        "grammatik": f"""Generálj 8 grammatika-drill feladatot.
Fókusz KIZÁRÓLAG: {top_weak}.
Váltogasd a fill_in és multiple_choice típusokat (4-4 darab).
Legyenek progresszíven nehezebbek.""",

        "vokabeln": f"""Generálj 8 szókincs feladatot a Linie B1.2 {chapter}. fejezetéhez.
Típusok: 4 fill_in (kontextusban), 4 multiple_choice (4 opció).
A szavak legyenek B1-B2 szintűek, hasznosak a mindennapokban.""",
    }

    vocab_hint = ""
    if session_type == "vokabeln" and due_vocab:
        words = [f"{w['german']} ({w['hungarian']})" for w in due_vocab[:5]]
        vocab_hint = f"\nEzeket a szavakat FELTÉTLENÜL szerepeltesd: {', '.join(words)}"

    prompt = f"""{type_prompts.get(session_type, type_prompts['lueckentext'])}{vocab_hint}

Adj vissza CSAK ezt a JSON struktúrát:
{{
  "session_type": "{session_type}",
  "title": "Session cím magyarul",
  "focus": "{top_weak}",
  "exercises": [
    {{
      "id": 1,
      "type": "fill_in",
      "instruction": "Egészítsd ki a mondatot!",
      "sentence": "Wenn er mehr Geld ___ (haben), würde er reisen.",
      "context": "Rövid kontextus vagy tipp (opcionális, lehet null)",
      "placeholder": "pl. hätte",
      "options": null,
      "correct_answer": "hätte",
      "grammar_note": "Konjunktiv II: haben → hätte"
    }},
    {{
      "id": 2,
      "type": "multiple_choice",
      "instruction": "Válaszd ki a helyes alakot!",
      "sentence": "Das Haus ___ gebaut.",
      "context": null,
      "placeholder": null,
      "options": ["wird", "ist", "hat", "war"],
      "correct_answer": "wird",
      "grammar_note": "Passiv Präsens: wird + Partizip II"
    }}
  ]
}}"""

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4000,
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    return _parse(text)


# ------------------------------------------------------------------ #
# Session evaluation                                                   #
# ------------------------------------------------------------------ #

def evaluate_session(
    exercises: list[dict],
    answers: list[str],
    session_type: str,
) -> dict:
    """Evaluate answers, return score, corrections, errors and new vocabulary."""
    pairs = []
    for ex, ans in zip(exercises, answers):
        pairs.append({
            "instruction": ex.get("instruction", ""),
            "sentence": ex.get("sentence") or ex.get("question", ""),
            "type": ex.get("type", ""),
            "correct_answer": ex.get("correct_answer", ""),
            "user_answer": ans or "(kihagyva)",
            "grammar_note": ex.get("grammar_note", ""),
        })

    prompt = f"""Értékeld ezt a "{session_type}" session-t. Légy biztató, de pontos.
Kisebb helyesírási hibák elfogadhatók, a grammatikai hibák nem.

{json.dumps(pairs, ensure_ascii=False, indent=2)}

Adj vissza CSAK ezt a JSON struktúrát:
{{
  "score": 75,
  "encouragement": "Biztató üzenet magyarul (1-2 mondat)",
  "summary": "Összefoglalás: mi ment jól, min kell dolgozni (2-3 mondat, magyarul)",
  "corrections": [
    {{
      "original": "pontosan amit a felhasználó írt",
      "correct": "helyes megoldás",
      "explanation": "miért helyes, röviden magyarul"
    }}
  ],
  "errors": [
    {{
      "category": "Konjunktiv II",
      "description": "a hiba rövid leírása"
    }}
  ],
  "new_vocabulary": [
    {{
      "german": "das Beispiel",
      "hungarian": "példa"
    }}
  ]
}}

A corrections CSAK a hibás vagy hiányos válaszokat tartalmazza.
A new_vocabulary az exercises-ben előforduló hasznos új szavakat listázza (max 5)."""

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    return _parse(text)


# ------------------------------------------------------------------ #
# Weekly summary                                                       #
# ------------------------------------------------------------------ #

def generate_weekly_summary(sessions: list[dict], error_cats: dict) -> str:
    """Return a motivating weekly progress summary in Hungarian."""
    stats = {
        "sessions_count": len(sessions),
        "avg_score": round(sum(s.get("score", 0) for s in sessions) / max(len(sessions), 1)),
        "types_done": list({s.get("session_type") for s in sessions}),
        "error_categories": {
            k: f"{v['wrong']}/{v['total']} hiba" for k, v in error_cats.items()
        },
    }

    prompt = f"""Írj egy rövid (4-6 mondat), biztató heti összefoglalót magyarul
a Deutsch-tanuló teljesítményéről:

{json.dumps(stats, ensure_ascii=False, indent=2)}

Emeld ki: mi ment jól, min kell még dolgozni, és adj egy konkrét tippet a következő hétre.
Ne használj JSON-t, csak szöveget írj."""

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=500,
        system=_system_cached(),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    return next((b.text for b in response.content if b.type == "text"), "")
