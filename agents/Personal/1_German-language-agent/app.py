"""Deutsch Üben – Streamlit app.

Deployment: Streamlit Cloud (free tier)
DB:         Supabase (free tier)
AI:         Anthropic claude-opus-4-7

cron-job.org emlékeztető:
  GET https://<app>.streamlit.app/?action=remind&token=<REMINDER_TOKEN>
"""

import os
import random
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ------------------------------------------------------------------ #
# Page config (must be first Streamlit call)                          #
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="🇩🇪 Deutsch Üben",
    page_icon="🇩🇪",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# Cron-job.org reminder endpoint                                       #
# Accessed as: ?action=remind&token=SECRET                            #
# ------------------------------------------------------------------ #
_params = st.query_params
if _params.get("action") == "remind":
    token = _params.get("token", "")
    expected = os.environ.get("REMINDER_TOKEN", "")
    if expected and token == expected:
        from database import Database
        from reminder import send_reminder

        _db = Database()
        _state = _db.get_user_state()
        _email = _state.get("email", "")
        if _email:
            ok = send_reminder(
                recipient_email=_email,
                session_count_today=len(_db.get_today_sessions()),
                streak=_state.get("current_streak", 0),
            )
            st.success("Emlékeztető elküldve." if ok else "Küldés sikertelen.")
        else:
            st.warning("Nincs beállítva email.")
    else:
        st.error("Érvénytelen token.")
    st.stop()

# ------------------------------------------------------------------ #
# Lazy imports (only after cron check)                                 #
# ------------------------------------------------------------------ #
from agent import (
    evaluate_assessment,
    evaluate_session,
    generate_assessment,
    generate_session,
    generate_weekly_summary,
)
from curriculum import CHAPTERS, GRAMMAR_CATEGORIES, SESSION_TYPES
from database import Database

# ------------------------------------------------------------------ #
# Shared state helpers                                                 #
# ------------------------------------------------------------------ #

@st.cache_resource
def get_db() -> Database:
    return Database()


db = get_db()


def go(page: str):
    st.session_state.page = page
    st.rerun()


def clear_session():
    for key in ["session_data", "session_type", "session_answers",
                "session_q_idx", "session_start", "session_eval"]:
        st.session_state.pop(key, None)


def clear_assessment():
    for key in ["assessment_questions", "assessment_answers",
                "assessment_q_idx", "assessment_started", "assessment_results"]:
        st.session_state.pop(key, None)


# ------------------------------------------------------------------ #
# Sidebar                                                              #
# ------------------------------------------------------------------ #

def render_sidebar(state: dict):
    with st.sidebar:
        st.markdown("## 🇩🇪 Deutsch Üben")
        st.markdown("---")

        streak = state.get("current_streak", 0)
        longest = state.get("longest_streak", 0)
        col1, col2 = st.columns(2)
        col1.metric("🔥 Streak", f"{streak} nap")
        col2.metric("🏆 Rekord", f"{longest} nap")

        st.markdown("---")
        st.markdown("**Fejlesztendő területek**")
        cats = db.get_error_categories()
        if cats:
            for cat, v in sorted(
                cats.items(),
                key=lambda x: x[1]["wrong"] / max(x[1]["total"], 1),
                reverse=True,
            )[:5]:
                if v["total"] > 0:
                    acc = int((1 - v["wrong"] / v["total"]) * 100)
                    bar_color = "🟢" if acc >= 75 else ("🟡" if acc >= 50 else "🔴")
                    st.write(f"{bar_color} **{cat}**: {acc}%")
        else:
            st.caption("A szintfelmérés után jelenik meg.")

        st.markdown("---")
        ch = state.get("current_chapter", 1)
        st.markdown(f"📖 **Fejezet {ch}:** {CHAPTERS.get(ch, {}).get('name', '')}")

        vocab_stats = db.get_vocabulary_stats()
        if vocab_stats["total"] > 0:
            st.markdown(f"🃏 **Szavak:** {vocab_stats['total']} db "
                        f"({vocab_stats['due_today']} esedékes ma)")

        st.markdown("---")
        if st.button("⚙️ Beállítások", use_container_width=True):
            go("settings")
        if st.button("📊 Statisztika", use_container_width=True):
            go("stats")
        if st.button("🏠 Főoldal", use_container_width=True):
            go("home")


# ------------------------------------------------------------------ #
# Assessment flow                                                      #
# ------------------------------------------------------------------ #

def page_assessment():
    st.title("📋 Szintfelmérés")

    # Step 0 – intro
    if "assessment_started" not in st.session_state:
        st.write("""
Üdvözlöm! Ez egy **B1–B2 szintfelmérő teszt**, amely meghatározza, hol tartasz pontosan,
és mely grammatikai területeken érdemes koncentrálni.

**A teszt tartalma:**
- Konjunktiv II, Passiv, Relativsätze
- Adjektivdeklination, Präpositionen
- Szókincs B1–B2 szinten

Kb. **10–15 perc**, 20 kérdés.
        """)
        if st.button("▶ Indítás", type="primary", use_container_width=True):
            with st.spinner("Teszt generálása (kb. 20 másodperc)..."):
                qs = generate_assessment()
            st.session_state.assessment_questions = qs
            st.session_state.assessment_answers = {}
            st.session_state.assessment_q_idx = 0
            st.session_state.assessment_started = True
            st.rerun()
        return

    qs = st.session_state.assessment_questions
    q_idx = st.session_state.assessment_q_idx

    # Step 1 – questions
    if q_idx < len(qs):
        q = qs[q_idx]
        st.progress(q_idx / len(qs), text=f"{q_idx + 1} / {len(qs)} kérdés")
        st.markdown(f"### {q['question']}")
        if q.get("context"):
            st.caption(q["context"])

        key = f"aq_{q_idx}"
        if q["type"] == "multiple_choice":
            answer = st.radio("Válaszd ki:", q.get("options") or [], key=key,
                              index=None)
        else:
            answer = st.text_input("Válaszod:", key=key, placeholder="Írd be a hiányzó szót")

        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button("Következő →", type="primary", use_container_width=True):
                st.session_state.assessment_answers[q_idx] = answer or ""
                st.session_state.assessment_q_idx = q_idx + 1
                st.rerun()
        with col2:
            if st.button("Kihagy"):
                st.session_state.assessment_answers[q_idx] = ""
                st.session_state.assessment_q_idx = q_idx + 1
                st.rerun()
        return

    # Step 2 – evaluate
    if "assessment_results" not in st.session_state:
        with st.spinner("Értékelés folyamatban (kb. 30 másodperc)..."):
            results = evaluate_assessment(qs, st.session_state.assessment_answers)
        db.save_assessment_results(results)
        st.session_state.assessment_results = results

    results = st.session_state.assessment_results
    st.success("✅ Szintfelmérés kész!")
    st.balloons()

    level = results.get("overall_level", "B1+")
    st.markdown(f"## Szinted: **{level}**")

    c1, c2, c3 = st.columns(3)
    c1.metric("Grammatika", f"{results.get('grammar_score', 0)}%")
    c2.metric("Szókincs", f"{results.get('vocabulary_score', 0)}%")
    c3.metric("Írás", f"{results.get('writing_score', 0)}%")

    if results.get("weaknesses"):
        st.markdown("**🔴 Fejlesztendő területek:**")
        for w in results["weaknesses"]:
            st.write(f"- {w}")

    if results.get("strengths"):
        st.markdown("**🟢 Erősségek:**")
        for s in results["strengths"]:
            st.write(f"- {s}")

    if results.get("summary"):
        st.info(results["summary"])

    if st.button("🚀 Kezdjük a napi gyakorlást!", type="primary", use_container_width=True):
        clear_assessment()
        go("home")


# ------------------------------------------------------------------ #
# Home / practice launcher                                             #
# ------------------------------------------------------------------ #

def page_home(state: dict):
    st.title("🇩🇪 Napi Gyakorlás")

    today_sessions = db.get_today_sessions()
    goal = 2

    # Progress banner
    col1, col2, col3 = st.columns(3)
    col1.metric("Mai session", f"{len(today_sessions)}/{goal}")
    col2.metric("🔥 Streak", f"{state.get('current_streak', 0)} nap")
    col3.metric("Átlag score", f"{_avg_score(today_sessions)}%")

    if len(today_sessions) >= goal:
        st.success("🎉 Mára elérted a napi célt! Fantasztikus munka!")

    st.markdown("---")

    # Session chooser
    st.subheader("Válassz egy feladatot")
    weakest = db.get_weakest_category()
    next_type = _pick_next_type(today_sessions, weakest)
    due_vocab = db.get_due_vocabulary(limit=8)

    cols = st.columns(len(SESSION_TYPES))
    for i, (stype, info) in enumerate(SESSION_TYPES.items()):
        with cols[i]:
            is_recommended = stype == next_type
            badge = " ⭐" if is_recommended else ""
            if st.button(
                f"{info['icon']}\n{info['label']}{badge}",
                use_container_width=True,
                type="primary" if is_recommended else "secondary",
                key=f"btn_{stype}",
            ):
                _start_session(stype, state, due_vocab)

    st.caption("⭐ = ajánlott a gyengeségeid alapján")

    # Today's sessions
    if today_sessions:
        st.markdown("---")
        st.subheader("Mai teljesítmény")
        for s in today_sessions:
            stype = s.get("session_type", "")
            icon = SESSION_TYPES.get(stype, {}).get("icon", "📚")
            score = s.get("score", 0)
            dur = s.get("duration_minutes", 0)
            score_color = "🟢" if score >= 75 else ("🟡" if score >= 50 else "🔴")
            st.write(f"{icon} **{SESSION_TYPES.get(stype, {}).get('label', stype)}** "
                     f"– {score_color} {score}% – {dur} perc")

    # Due vocabulary reminder
    if due_vocab and "vokabeln" not in {s.get("session_type") for s in today_sessions}:
        st.info(f"🃏 {len(due_vocab)} szó vár ismétlésre ma!")


def _start_session(stype: str, state: dict, due_vocab: list):
    with st.spinner(f"Feladatok generálása ({SESSION_TYPES[stype]['label']})..."):
        session_data = generate_session(
            session_type=stype,
            chapter=state.get("current_chapter", 1),
            weaknesses=db.get_error_categories(),
            due_vocab=due_vocab if stype == "vokabeln" else None,
        )
    st.session_state.session_data = session_data
    st.session_state.session_type = stype
    st.session_state.session_answers = []
    st.session_state.session_q_idx = 0
    st.session_state.session_start = datetime.now()
    go("session")


def _pick_next_type(today_sessions: list, weakest: str | None) -> str:
    used = {s.get("session_type") for s in today_sessions}
    order = ["grammatik", "lueckentext", "fehlerkorrektur", "schreiben", "vokabeln"]
    if weakest and "grammatik" not in used:
        return "grammatik"
    for t in order:
        if t not in used:
            return t
    return random.choice(list(SESSION_TYPES.keys()))


def _avg_score(sessions: list) -> int:
    if not sessions:
        return 0
    return round(sum(s.get("score", 0) for s in sessions) / len(sessions))


# ------------------------------------------------------------------ #
# Active session                                                       #
# ------------------------------------------------------------------ #

def page_session():
    session_data = st.session_state.get("session_data", {})
    stype = st.session_state.get("session_type", "")
    exercises = session_data.get("exercises", [])
    q_idx = st.session_state.get("session_q_idx", 0)
    answers = st.session_state.get("session_answers", [])

    info = SESSION_TYPES.get(stype, {})
    st.title(f"{info.get('icon', '📚')} {session_data.get('title', info.get('label', ''))}")
    focus = session_data.get("focus", "")
    if focus:
        st.caption(f"Fókusz: {focus}")

    # ---- Results screen ----
    if "session_eval" in st.session_state:
        _render_results(stype)
        return

    # ---- Evaluate trigger ----
    if q_idx >= len(exercises):
        with st.spinner("Értékelés... (kb. 20 másodperc)"):
            evaluation = evaluate_session(exercises, answers, stype)
        duration = max(1, int((datetime.now() - st.session_state.session_start).seconds / 60))
        db.save_session({
            "session_type": stype,
            "score": evaluation.get("score", 0),
            "duration_minutes": duration,
            "errors": evaluation.get("errors", []),
        })
        db.update_streak()
        for word in evaluation.get("new_vocabulary", []):
            db.add_vocabulary(word)
        st.session_state.session_eval = evaluation
        st.rerun()
        return

    # ---- Exercise ----
    ex = exercises[q_idx]
    st.progress(q_idx / len(exercises), text=f"Feladat {q_idx + 1} / {len(exercises)}")
    st.markdown(f"#### {ex.get('instruction', 'Egészítsd ki!')}")

    sentence = ex.get("sentence") or ex.get("question", "")
    if sentence:
        st.markdown(f"> {sentence}")

    if ex.get("context"):
        st.info(ex["context"])

    if ex.get("grammar_note"):
        with st.expander("💡 Tipp"):
            st.write(ex["grammar_note"])

    key = f"ex_{q_idx}"
    if ex.get("type") == "multiple_choice" and ex.get("options"):
        answer = st.radio("Válaszd ki:", ex["options"], key=key, index=None)
    elif ex.get("type") == "writing":
        answer = st.text_area(
            "Írj 3-5 mondatot:", key=key, height=130,
            placeholder=ex.get("placeholder") or "Schreib auf Deutsch..."
        )
    else:
        answer = st.text_input(
            "Válaszod:", key=key,
            placeholder=ex.get("placeholder") or "Írd be a választ"
        )

    c1, c2 = st.columns([5, 1])
    with c1:
        if st.button("Következő →", type="primary", use_container_width=True):
            st.session_state.session_answers.append(answer or "")
            st.session_state.session_q_idx = q_idx + 1
            st.rerun()
    with c2:
        if st.button("⏭"):
            st.session_state.session_answers.append("")
            st.session_state.session_q_idx = q_idx + 1
            st.rerun()


def _render_results(stype: str):
    ev = st.session_state.session_eval
    score = ev.get("score", 0)
    emoji = "🎉" if score >= 80 else ("👍" if score >= 60 else "💪")

    st.markdown(f"## {emoji} Eredmény: {score}%")

    if ev.get("encouragement"):
        st.success(ev["encouragement"])

    if ev.get("summary"):
        st.write(ev["summary"])

    corrections = ev.get("corrections", [])
    if corrections:
        st.markdown("### ✏️ Javítások")
        for c in corrections:
            with st.container(border=True):
                st.markdown(f"**❌ Tévesen:** {c.get('original', '')}")
                st.markdown(f"**✅ Helyesen:** {c.get('correct', '')}")
                if c.get("explanation"):
                    st.caption(c["explanation"])

    new_words = ev.get("new_vocabulary", [])
    if new_words:
        st.markdown("### 🔤 Új szavak")
        for w in new_words:
            st.write(f"**{w.get('german', '')}** – {w.get('hungarian', '')}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🏠 Főoldal", use_container_width=True):
            clear_session()
            go("home")
    with c2:
        if st.button("▶ Még egy kör!", type="primary", use_container_width=True):
            stype_next = stype
            clear_session()
            state = db.get_user_state()
            due_vocab = db.get_due_vocabulary()
            _start_session(stype_next, state, due_vocab)


# ------------------------------------------------------------------ #
# Stats page                                                           #
# ------------------------------------------------------------------ #

def page_stats():
    st.title("📊 Statisztika")
    state = db.get_user_state()

    st.metric("🔥 Streak", f"{state.get('current_streak', 0)} nap")
    st.metric("🏆 Leghosszabb streak", f"{state.get('longest_streak', 0)} nap")

    sessions = db.get_sessions_last_n_days(14)
    if sessions:
        st.markdown(f"**Elmúlt 14 nap: {len(sessions)} session, átlag {_avg_score(sessions)}%**")

        # Type breakdown
        from collections import defaultdict
        by_type: dict = defaultdict(list)
        for s in sessions:
            by_type[s.get("session_type", "?")].append(s.get("score", 0))

        st.markdown("### Session típusonként")
        for stype, scores in by_type.items():
            label = SESSION_TYPES.get(stype, {}).get("label", stype)
            icon = SESSION_TYPES.get(stype, {}).get("icon", "📚")
            avg = round(sum(scores) / len(scores))
            st.write(f"{icon} **{label}**: {len(scores)} alkalom, átlag **{avg}%**")

    st.markdown("### Grammatika kategóriák")
    cats = db.get_error_categories()
    if cats:
        for cat, v in sorted(cats.items(),
                             key=lambda x: x[1]["wrong"] / max(x[1]["total"], 1),
                             reverse=True):
            if v["total"] > 0:
                acc = int((1 - v["wrong"] / v["total"]) * 100)
                st.write(f"**{cat}**: {v['wrong']} hiba / {v['total']} próba ({acc}% helyes)")
    else:
        st.info("Még nincs adat. Csináld az első sessiont!")

    st.markdown("### Szókincs")
    vocab_stats = db.get_vocabulary_stats()
    st.write(f"Összesen: **{vocab_stats['total']}** szó, "
             f"ma esedékes: **{vocab_stats['due_today']}**")

    if sessions:
        st.markdown("---")
        if st.button("📝 Heti összefoglaló generálása"):
            with st.spinner("Összefoglaló írása..."):
                summary = generate_weekly_summary(sessions, cats)
            st.write(summary)


# ------------------------------------------------------------------ #
# Settings page                                                        #
# ------------------------------------------------------------------ #

def page_settings(state: dict):
    st.title("⚙️ Beállítások")

    st.subheader("Linie B1.2 – aktuális fejezet")
    ch = st.selectbox(
        "Melyik fejezetnél tartasz?",
        options=list(CHAPTERS.keys()),
        format_func=lambda x: f"Kapitel {x}: {CHAPTERS[x]['name']}",
        index=state.get("current_chapter", 1) - 1,
    )

    st.subheader("Email emlékeztető")
    email = st.text_input(
        "Email cím",
        value=state.get("email", ""),
        placeholder="nev@gmail.com",
    )
    st.caption(
        "A cron-job.org naponta 2x elküldi az emlékeztetőt erre a címre. "
        "Gmail-t ajánlott használni."
    )

    if st.button("💾 Mentés", type="primary"):
        db.update_settings({"current_chapter": ch, "email": email})
        st.success("Beállítások elmentve!")

    st.markdown("---")
    st.subheader("🔄 Szintfelmérés újraindítása")
    st.warning("Ez törli az értékelési adatokat (a session-ok megmaradnak).")
    if st.checkbox("Igen, biztosan újra akarom csinálni"):
        if st.button("Szintfelmérés újraindítása", type="secondary"):
            db.reset_assessment()
            clear_assessment()
            st.success("Szintfelmérés törölve. Frissítsd az oldalt.")


# ------------------------------------------------------------------ #
# Router                                                               #
# ------------------------------------------------------------------ #

def main():
    state = db.get_user_state()
    render_sidebar(state)

    page = st.session_state.get("page", "home")

    # Settings always accessible
    if page == "settings":
        page_settings(state)
        return

    # Assessment gate
    if not state.get("assessment_done"):
        page_assessment()
        return

    if page == "session" and "session_data" in st.session_state:
        page_session()
    elif page == "stats":
        page_stats()
    elif page == "settings":
        page_settings(state)
    else:
        st.session_state.page = "home"
        page_home(state)


if __name__ == "__main__":
    main()
