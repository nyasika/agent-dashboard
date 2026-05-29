CHAPTERS = {
    1: {
        "name": "Reisen und Mobilität",
        "topics": ["Verkehrsmittel", "Reiseerlebnisse", "Stadtplanung", "Orientierung"],
        "key_vocab": ["die Reise", "der Bahnhof", "das Flugzeug", "umsteigen", "ankommen",
                      "die Verspätung", "der Fahrplan", "reservieren", "die Unterkunft"],
        "grammar_focus": "Konjunktiv II – Wünsche und Möglichkeiten",
    },
    2: {
        "name": "Gesundheit und Körper",
        "topics": ["Gesundheitsvorsorge", "Ernährung", "Sport", "Arztbesuch"],
        "key_vocab": ["die Gesundheit", "das Rezept", "die Apotheke", "sich erholen",
                      "behandeln", "die Beschwerde", "der Schmerz", "sich impfen lassen"],
        "grammar_focus": "Passiv (Präsens, Präteritum, Perfekt)",
    },
    3: {
        "name": "Medien und Kommunikation",
        "topics": ["Soziale Medien", "Nachrichten", "Digitalisierung", "Werbung"],
        "key_vocab": ["die Nachricht", "veröffentlichen", "teilen", "der Einfluss",
                      "berichten", "das Netzwerk", "hochladen", "der Kommentar"],
        "grammar_focus": "Relativsätze (Nominativ, Akkusativ, Dativ)",
    },
    4: {
        "name": "Arbeit und Beruf",
        "topics": ["Bewerbung", "Arbeitsalltag", "Berufswahl", "Homeoffice"],
        "key_vocab": ["die Bewerbung", "das Vorstellungsgespräch", "der Lebenslauf",
                      "kündigen", "einstellen", "die Gehaltsverhandlung", "die Stelle"],
        "grammar_focus": "Kausale und konzessive Nebensätze (weil, obwohl, da, trotzdem)",
    },
    5: {
        "name": "Umwelt und Natur",
        "topics": ["Klimawandel", "Nachhaltigkeit", "Naturschutz", "Energie"],
        "key_vocab": ["der Klimawandel", "nachhaltig", "recyceln", "der Naturschutz",
                      "umweltfreundlich", "die Emissionen", "erneuerbar", "schützen"],
        "grammar_focus": "Finalsätze und Konsekutivsätze (damit, sodass, um…zu)",
    },
    6: {
        "name": "Gesellschaft und Zukunft",
        "topics": ["Generationen", "Technologie", "Globalisierung", "Integration"],
        "key_vocab": ["die Gesellschaft", "die Generation", "verändern", "global",
                      "die Zukunft", "die Integration", "vielfältig", "der Fortschritt"],
        "grammar_focus": "Partizipien als Adjektive und Nominalstil",
    },
}

GRAMMAR_CATEGORIES = {
    "Konjunktiv II": {
        "description": "Wünsche, Möglichkeiten, höfliche Bitten",
        "examples": ["Ich würde gerne...", "Könnten Sie...?", "Wenn ich Zeit hätte,..."],
        "difficulty": "B1-B2",
        "common_forms": ["würde", "wäre", "hätte", "könnte", "sollte", "müsste", "dürfte"],
    },
    "Passiv": {
        "description": "Passiv Präsens, Präteritum und Perfekt",
        "examples": ["Das Haus wird gebaut.", "Das Buch wurde geschrieben.",
                     "Das Formular ist ausgefüllt worden."],
        "difficulty": "B1",
        "common_forms": ["wird/werden + Partizip II", "wurde/wurden + Partizip II",
                         "ist/sind + Partizip II + worden"],
    },
    "Relativsätze": {
        "description": "Relativpronomen in allen Kasus",
        "examples": ["Der Mann, der...", "Das Buch, das...", "Die Frau, der ich...",
                     "Das Kind, dem ich...", "Das Haus, dessen Garten..."],
        "difficulty": "B1",
    },
    "Adjektivdeklination": {
        "description": "Adjektive mit bestimmtem, unbestimmtem Artikel und ohne Artikel",
        "examples": ["der alte Mann", "ein alter Mann", "alter Mann",
                     "die schöne Frau", "eine schöne Frau"],
        "difficulty": "B1",
    },
    "Trennbare Verben": {
        "description": "Trennbare und untrennbare Verben korrekt verwenden",
        "examples": ["ankommen → Ich komme an.", "aufstehen → Er steht auf.",
                     "verstehen → Ich verstehe.", "vorstellen → Stell dich vor!"],
        "difficulty": "B1",
    },
    "Präpositionen": {
        "description": "Wechselpräpositionen (Dativ/Akkusativ) und feste Verbpräpositionen",
        "examples": ["Ich sitze auf dem Stuhl. / Ich setze mich auf den Stuhl.",
                     "denken an + Akk.", "warten auf + Akk.", "sich freuen über + Akk."],
        "difficulty": "B1-B2",
    },
    "Perfekt vs. Präteritum": {
        "description": "Gesprochenes (Perfekt) vs. Geschriebenes (Präteritum) Deutsch",
        "examples": ["Ich habe gegessen. (gesprochen)", "Ich aß. (geschrieben)",
                     "Er ist gegangen. / Er ging."],
        "difficulty": "B1",
    },
    "Nebensätze": {
        "description": "Kausale, konzessive, finale und temporale Nebensätze",
        "examples": ["weil/da (kausal)", "obwohl/obgleich (konzessiv)",
                     "damit/um…zu (final)", "als/wenn/nachdem (temporal)"],
        "difficulty": "B1-B2",
    },
    "Nominalstil": {
        "description": "Verben in Nomen umwandeln (Schriftsprache B2)",
        "examples": ["Die Entscheidung wurde getroffen.",
                     "Nach der Ankunft...", "Aufgrund der Verspätung..."],
        "difficulty": "B2",
    },
}

SESSION_TYPES = {
    "lueckentext": {
        "label": "Lückentext",
        "icon": "📝",
        "description": "Töltsd ki a hiányzó szavakat",
        "count": 6,
    },
    "fehlerkorrektur": {
        "label": "Fehlerkorrektur",
        "icon": "✏️",
        "description": "Javítsd ki a hibás mondatokat",
        "count": 6,
    },
    "schreiben": {
        "label": "Freies Schreiben",
        "icon": "📖",
        "description": "Írj 3-5 mondatot egy adott témáról",
        "count": 3,
    },
    "grammatik": {
        "label": "Grammatik-Drill",
        "icon": "🔧",
        "description": "Intenzív grammatika gyakorlás a gyenge területeken",
        "count": 8,
    },
    "vokabeln": {
        "label": "Vokabeln",
        "icon": "🃏",
        "description": "Szókincs ismétlés (spaced repetition)",
        "count": 8,
    },
}
