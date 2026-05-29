"""Bia Államvizsga Segéd – Streamlit app."""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="Bia Államvizsga",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

from tetelek import load_all, pick_weighted, tetel_list_summary
from agent import generate_questions, evaluate_answer, summarize_session

# Supabase opcionális — app DB nélkül is fut
try:
    from database import (
        get_confidence_map, save_confidence,
        increment_practice_count, save_session, get_stats,
    )
    DB_OK = True
except Exception:
    DB_OK = False


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

@st.cache_data
def get_tetelek():
    return load_all()


def go(page: str):
    st.session_state.page = page
    st.rerun()


def conf_map() -> dict[int, int]:
    if DB_OK:
        try:
            return get_confidence_map()
        except Exception:
            pass
    return st.session_state.get("local_conf", {})


def save_conf_local(tetel_id: int, weight: int):
    lc = st.session_state.get("local_conf", {})
    lc[tetel_id] = weight
    st.session_state["local_conf"] = lc


def clear_session():
    for k in ["tetel", "session_type", "kerdesek", "q_idx",
              "valaszok", "ertekelesek", "session_start", "summary"]:
        st.session_state.pop(k, None)


CONFIDENCE_OPTS = [
    (4, "Nem tudtam"),
    (3, "Bizonytalanul"),
    (2, "Jól ment"),
    (1, "Magabiztosan"),
]

SESSION_LABELS = {
    "attekintes":       ("📖", "Áttekintés"),
    "fogalmak":         ("🔤", "Fogalmak"),
    "vizsgaszimulator": ("🎤", "Vizsgaszimulátor"),
}


# ------------------------------------------------------------------ #
# Sidebar                                                              #
# ------------------------------------------------------------------ #

def render_sidebar():
    tetelek = get_tetelek()
    cm = conf_map()

    with st.sidebar:
        st.markdown("## 🎓 Bia Államvizsga")
        st.markdown("---")

        total = len(tetelek)
        practiced = len(cm)
        strong = sum(1 for w in cm.values() if w <= 2)
        weak = sum(1 for w in cm.values() if w >= 3)

        c1, c2 = st.columns(2)
        c1.metric("Gyakorolt", f"{practiced}/{total}")
        c2.metric("Biztos", f"{strong}")

        if weak:
            st.warning(f"⚠️ {weak} tétel még nem biztos")

        st.markdown("---")
        st.markdown("**Tételek állapota**")
        summary = tetel_list_summary(tetelek, cm)
        colors = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", None: "⚪"}
        for item in summary:
            col = colors.get(item["confidence"])
            label = item["confidence_label"]
            st.caption(f"{col} **{item['id']}.** {item['cim'][:35]}… — {label}")

        st.markdown("---")
        if st.button("📊 Statisztika", use_container_width=True):
            go("stats")
        if st.button("🏠 Főoldal", use_container_width=True):
            clear_session()
            go("home")


# ------------------------------------------------------------------ #
# Home — tétel választó                                               #
# ------------------------------------------------------------------ #

def page_home():
    tetelek = get_tetelek()
    cm = conf_map()
    all_ids = sorted(tetelek.keys())

    st.title("🎓 Bia Államvizsga Segéd")
    st.markdown("Válassz tanulásmódot!")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🎲 Véletlenszerű húzás")
        st.caption("Súlyozva a gyengébb tételek felé.")
        if st.button("Tétel húzása", type="primary", use_container_width=True):
            tid = pick_weighted(cm, all_ids)
            st.session_state.tetel = tetelek[tid]
            go("tetel")

    with col2:
        st.subheader("📋 Tétel választása")
        st.caption("Válaszd ki melyiket szeretnéd gyakorolni.")
        options = {f"{t['id']}. {t['cim']}": t['id'] for t in tetelek.values()}
        selected = st.selectbox("Tétel:", list(options.keys()), label_visibility="collapsed")
        if st.button("Megnyitás", use_container_width=True):
            tid = options[selected]
            st.session_state.tetel = tetelek[tid]
            go("tetel")

    st.markdown("---")
    st.markdown("**Leggyengébb tételek**")
    weak_ids = sorted([tid for tid, w in cm.items() if w >= 3],
                      key=lambda t: cm.get(t, 3), reverse=True)[:5]
    if weak_ids:
        cols = st.columns(min(len(weak_ids), 5))
        for i, tid in enumerate(weak_ids):
            with cols[i]:
                t = tetelek[tid]
                if st.button(f"**{tid}.**\n{t['cim'][:20]}…",
                             use_container_width=True, key=f"weak_{tid}"):
                    st.session_state.tetel = t
                    go("tetel")
    else:
        st.info("Még nincs elég adat. Kezdj el gyakorolni!")


# ------------------------------------------------------------------ #
# Tétel nézet                                                          #
# ------------------------------------------------------------------ #

def page_tetel():
    t = st.session_state.get("tetel")
    if not t:
        go("home")
        return

    cm = conf_map()
    prev_conf = cm.get(t["id"])
    conf_label = {1: "🟢 Magabiztos", 2: "🟡 Jól ment",
                  3: "🟠 Bizonytalan", 4: "🔴 Nem tudtam"}.get(prev_conf, "⚪ Nem gyakorolt")

    st.title(f"Tétel {t['id']}: {t['cim']}")
    st.caption(f"Korábbi értékelés: {conf_label}")
    st.markdown("---")

    # Összefoglaló
    with st.expander("📝 Összefoglaló", expanded=True):
        st.write(t.get("osszefoglalo", ""))
        if t.get("kulcsfogalmak"):
            st.markdown("**Kulcsfogalmak:** " +
                        " · ".join(f"`{k}`" for k in t["kulcsfogalmak"]))

    # Képek
    kepek = [k for k in t.get("kepek", []) if k.get("fajl")]
    if kepek:
        with st.expander(f"🖼️ Ábrák ({len(kepek)} db)"):
            cols_per_row = 2
            for i in range(0, len(kepek), cols_per_row):
                row = kepek[i:i + cols_per_row]
                cols = st.columns(len(row))
                for col, kep in zip(cols, row):
                    img_path = Path(__file__).parent / kep["fajl"]
                    if img_path.exists():
                        with col:
                            st.image(str(img_path),
                                     caption=f"{kep['sorszam']}. ábra",
                                     use_container_width=True)

    # Teljes szöveg
    with st.expander("📄 Teljes szöveg"):
        st.text(t.get("szoveg", ""))

    st.markdown("---")
    st.subheader("Mód választása")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📖 Áttekintés**")
        st.caption("Összefoglaló + képek megtekintése. Nincs értékelés.")
        if st.button("Áttekintés", use_container_width=True, key="btn_att"):
            _start_session("attekintes")
    with c2:
        st.markdown("**🔤 Fogalmak**")
        st.caption("5 fogalom-definíciós kérdés. Rövid válaszok.")
        if st.button("Fogalmak", use_container_width=True, key="btn_fog"):
            _start_session("fogalmak")
    with c3:
        st.markdown("**🎤 Vizsgaszimulátor**")
        st.caption("5 szóbeli kérdés, AI értékelés. Legintenzívebb.")
        if st.button("Vizsgaszimulátor", type="primary",
                     use_container_width=True, key="btn_viz"):
            _start_session("vizsgaszimulator")

    st.markdown("---")
    if st.button("← Főoldal", use_container_width=True):
        clear_session()
        go("home")


def _start_session(session_type: str):
    t = st.session_state.tetel
    if session_type == "attekintes":
        if DB_OK:
            try:
                increment_practice_count(t["id"])
            except Exception:
                pass
        go("tetel")
        return

    with st.spinner("Kérdések generálása…"):
        kerdesek = generate_questions(t, session_type)

    st.session_state.session_type = session_type
    st.session_state.kerdesek = kerdesek
    st.session_state.q_idx = 0
    st.session_state.valaszok = []
    st.session_state.ertekelesek = []
    st.session_state.session_start = datetime.now()
    go("session")


# ------------------------------------------------------------------ #
# Session — kérdés-válasz loop                                         #
# ------------------------------------------------------------------ #

def page_session():
    t = st.session_state.get("tetel")
    kerdesek = st.session_state.get("kerdesek", [])
    q_idx = st.session_state.get("q_idx", 0)
    session_type = st.session_state.get("session_type", "vizsgaszimulator")

    if not t or not kerdesek:
        go("home")
        return

    icon, label = SESSION_LABELS.get(session_type, ("📚", "Gyakorlás"))
    st.title(f"{icon} {label} — {t['cim']}")

    # Értékelés után
    if "summary" in st.session_state:
        _render_results()
        return

    # Összes kérdés megválaszolva → értékelés
    if q_idx >= len(kerdesek):
        with st.spinner("Értékelés folyamatban…"):
            valaszok = st.session_state.valaszok
            ertekelesek = []
            for kerd, val in zip(kerdesek, valaszok):
                ev = evaluate_answer(t, kerd["kerdes"], val)
                ertekelesek.append(ev)
            st.session_state.ertekelesek = ertekelesek
            summary = summarize_session(t, kerdesek, ertekelesek)
            st.session_state.summary = summary

            duration = max(1, int(
                (datetime.now() - st.session_state.session_start).seconds / 60))
            if DB_OK:
                try:
                    save_session(t["id"], session_type,
                                 summary.get("atlag_score"), duration)
                except Exception:
                    pass
        st.rerun()
        return

    # Aktuális kérdés
    kerd = kerdesek[q_idx]
    st.progress((q_idx) / len(kerdesek),
                text=f"Kérdés {q_idx + 1} / {len(kerdesek)}")

    st.markdown(f"### {kerd['kerdes']}")

    if kerd.get("segedfogalmak"):
        with st.expander("💡 Segítség (érintőpontok)"):
            for f in kerd["segedfogalmak"]:
                st.write(f"- {f}")

    answer = st.text_area(
        "Válaszod (úgy, ahogy szóban mondanád):",
        key=f"ans_{q_idx}",
        height=150,
        placeholder="Fejtsd ki részletesen…",
    )

    c1, c2 = st.columns([5, 1])
    with c1:
        if st.button("Következő →", type="primary", use_container_width=True):
            st.session_state.valaszok.append(answer or "(kihagyva)")
            st.session_state.q_idx = q_idx + 1
            st.rerun()
    with c2:
        if st.button("⏭ Kihagy"):
            st.session_state.valaszok.append("(kihagyva)")
            st.session_state.q_idx = q_idx + 1
            st.rerun()


# ------------------------------------------------------------------ #
# Eredmények + confidence picker                                       #
# ------------------------------------------------------------------ #

def _render_results():
    t = st.session_state.tetel
    summary = st.session_state.summary
    ertekelesek = st.session_state.get("ertekelesek", [])
    kerdesek = st.session_state.get("kerdesek", [])

    score = summary.get("atlag_score", 0)
    emoji = "🎉" if score >= 80 else ("👍" if score >= 60 else "💪")

    st.markdown(f"## {emoji} Eredmény: {score}%")

    if summary.get("dicseret"):
        st.success(summary["dicseret"])
    if summary.get("osszefoglalo"):
        st.write(summary["osszefoglalo"])

    if summary.get("fo_gyengesegek"):
        st.markdown("**🔴 Főbb hiányosságok:**")
        for gy in summary["fo_gyengesegek"]:
            st.write(f"- {gy}")

    # Részletes értékelések
    if ertekelesek:
        st.markdown("---")
        st.markdown("### Részletes visszajelzés")
        for i, (kerd, ev) in enumerate(zip(kerdesek, ertekelesek), 1):
            q_score = ev.get("score", 0)
            color = "🟢" if q_score >= 75 else ("🟡" if q_score >= 50 else "🔴")
            with st.expander(f"{color} {i}. kérdés – {q_score}%"):
                st.markdown(f"**Kérdés:** {kerd['kerdes']}")
                st.markdown(f"**Értékelés:** {ev.get('ertekeles', '')}")
                if ev.get("helyes_pontok"):
                    st.markdown("✅ **Jól tudtad:** " +
                                " · ".join(ev["helyes_pontok"]))
                if ev.get("hianyzo_pontok"):
                    st.markdown("❌ **Hiányzott:** " +
                                " · ".join(ev["hianyzo_pontok"]))
                if ev.get("pontositas"):
                    st.info(f"📌 {ev['pontositas']}")

    # Confidence picker
    st.markdown("---")
    st.markdown("### Hogy érezted magad ennél a tételnél?")
    st.caption("Ez befolyásolja, hogy mennyire kerül elő a véletlen húzásnál.")

    conf_cols = st.columns(4)
    for col, (weight, label) in zip(conf_cols, CONFIDENCE_OPTS):
        if col.button(label, use_container_width=True, key=f"conf_{weight}"):
            if DB_OK:
                try:
                    save_confidence(t["id"], weight)
                except Exception:
                    save_conf_local(t["id"], weight)
            else:
                save_conf_local(t["id"], weight)
            st.success(f"Mentve: {label}")
            st.rerun()

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🏠 Főoldal", use_container_width=True):
            clear_session()
            go("home")
    with c2:
        if st.button("🔄 Újra ezt a tételt", type="primary",
                     use_container_width=True):
            session_type = st.session_state.get("session_type", "vizsgaszimulator")
            clear_session()
            st.session_state.tetel = t
            _start_session(session_type)


# ------------------------------------------------------------------ #
# Stats                                                                #
# ------------------------------------------------------------------ #

def page_stats():
    st.title("📊 Statisztika")
    cm = conf_map()
    tetelek = get_tetelek()

    col1, col2, col3 = st.columns(3)
    col1.metric("Összes tétel", len(tetelek))
    col2.metric("Gyakorolt", len(cm))
    col3.metric("Biztos tudás", sum(1 for w in cm.values() if w <= 2))

    if DB_OK:
        try:
            stats = get_stats()
            st.metric("Összes session", stats["total_sessions"])
            if stats["avg_score"]:
                st.metric("Átlag pontszám", f"{stats['avg_score']}%")
        except Exception:
            pass

    st.markdown("---")
    st.markdown("### Tétel állapotok")
    colors = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", None: "⚪"}
    labels = {1: "Magabiztos", 2: "Jól ment", 3: "Bizonytalan",
              4: "Nem tudtam", None: "Nem gyakorolt"}

    summary = tetel_list_summary(tetelek, cm)
    for item in summary:
        c = colors[item["confidence"]]
        l = labels[item["confidence"]]
        st.write(f"{c} **{item['id']}.** {item['cim']} — *{l}*")

    st.markdown("---")
    if st.button("🏠 Főoldal", use_container_width=True):
        go("home")


# ------------------------------------------------------------------ #
# Router                                                               #
# ------------------------------------------------------------------ #

def main():
    render_sidebar()
    page = st.session_state.get("page", "home")

    if page == "tetel" and "tetel" in st.session_state:
        page_tetel()
    elif page == "session":
        page_session()
    elif page == "stats":
        page_stats()
    else:
        st.session_state.page = "home"
        page_home()


if __name__ == "__main__":
    main()
