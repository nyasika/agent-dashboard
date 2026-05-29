"""Supabase adatbázis réteg — haladás és confidence tracking."""

import os
from datetime import date, datetime

from supabase import create_client, Client


def _get_supabase_creds() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        try:
            import streamlit as st
            url = url or st.secrets.get("SUPABASE_URL")
            key = key or st.secrets.get("SUPABASE_KEY")
        except Exception:
            pass
    return url, key

# ------------------------------------------------------------------ #
# Supabase séma (egyszer kell futtatni a Supabase SQL editorban):
#
# create table user_state (
#   id integer primary key default 1,
#   check (id = 1),          -- egyetlen sor
#   streak integer default 0,
#   longest_streak integer default 0,
#   last_practice_date date
# );
# insert into user_state (id) values (1) on conflict do nothing;
#
# create table sessions (
#   id bigserial primary key,
#   tetel_id integer not null,
#   session_type text not null,   -- 'attekintes' | 'fogalmak' | 'vizsgaszimulator'
#   score integer,                -- 0-100, null ha nem értékelt
#   confidence integer,           -- 1-4, user visszajelzés
#   duration_minutes integer,
#   created_at timestamptz default now()
# );
#
# create table tetel_confidence (
#   tetel_id integer primary key,
#   weight integer not null default 3,  -- 1=Magabiztos .. 4=Nem tudtam
#   last_practiced date,
#   practice_count integer default 0
# );
# ------------------------------------------------------------------ #

_client: Client | None = None


def _db() -> Client:
    global _client
    if _client is None:
        url, key = _get_supabase_creds()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL vagy SUPABASE_KEY hiányzik")
        _client = create_client(url, key)
    return _client


# ------------------------------------------------------------------ #
# Confidence                                                           #
# ------------------------------------------------------------------ #

def get_confidence_map() -> dict[int, int]:
    """Visszatér: {tetel_id: weight} az összes értékelt tételre."""
    rows = _db().table("tetel_confidence").select("tetel_id, weight").execute().data
    return {r["tetel_id"]: r["weight"] for r in rows}


def save_confidence(tetel_id: int, weight: int) -> None:
    """Elmenti vagy frissíti a tétel confidence értékét."""
    _db().table("tetel_confidence").upsert({
        "tetel_id": tetel_id,
        "weight": weight,
        "last_practiced": date.today().isoformat(),
    }, on_conflict="tetel_id").execute()

    _db().table("tetel_confidence").update({
        "practice_count": _db().table("tetel_confidence")
            .select("practice_count")
            .eq("tetel_id", tetel_id)
            .single()
            .execute()
            .data["practice_count"] + 1
    }).eq("tetel_id", tetel_id).execute()


def increment_practice_count(tetel_id: int) -> None:
    rows = _db().table("tetel_confidence").select("practice_count").eq("tetel_id", tetel_id).execute().data
    current = rows[0]["practice_count"] if rows else 0
    _db().table("tetel_confidence").upsert({
        "tetel_id": tetel_id,
        "practice_count": current + 1,
        "last_practiced": date.today().isoformat(),
    }, on_conflict="tetel_id").execute()


# ------------------------------------------------------------------ #
# Sessions                                                             #
# ------------------------------------------------------------------ #

def save_session(tetel_id: int, session_type: str, score: int | None,
                 duration_minutes: int) -> None:
    _db().table("sessions").insert({
        "tetel_id": tetel_id,
        "session_type": session_type,
        "score": score,
        "duration_minutes": duration_minutes,
    }).execute()


def get_recent_sessions(limit: int = 20) -> list[dict]:
    return _db().table("sessions").select("*").order(
        "created_at", desc=True
    ).limit(limit).execute().data


def get_sessions_for_tetel(tetel_id: int) -> list[dict]:
    return _db().table("sessions").select("*").eq(
        "tetel_id", tetel_id
    ).order("created_at", desc=True).execute().data


# ------------------------------------------------------------------ #
# Stats                                                                #
# ------------------------------------------------------------------ #

def get_stats() -> dict:
    """Összesített statisztikák a stats oldalhoz."""
    conf_rows = _db().table("tetel_confidence").select("*").execute().data
    session_rows = _db().table("sessions").select("*").execute().data

    practiced = len(conf_rows)
    not_practiced = 30 - practiced

    weak = [r for r in conf_rows if r["weight"] >= 3]
    strong = [r for r in conf_rows if r["weight"] <= 2]

    avg_score = 0
    scored = [s["score"] for s in session_rows if s.get("score") is not None]
    if scored:
        avg_score = round(sum(scored) / len(scored))

    return {
        "total_sessions": len(session_rows),
        "practiced_tetelek": practiced,
        "not_practiced": not_practiced,
        "weak_count": len(weak),
        "strong_count": len(strong),
        "avg_score": avg_score,
        "confidence_rows": conf_rows,
    }
