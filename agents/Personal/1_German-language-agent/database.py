"""Supabase persistence layer.

Tables required (run setup_db() once, or paste the SQL from SETUP.md):
  user_state, sessions, error_categories, vocabulary
"""

import os
from datetime import date, datetime, timedelta
from typing import Optional

from supabase import create_client, Client


def _client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


class Database:
    def __init__(self):
        self.db = _client()

    # ------------------------------------------------------------------ #
    # User state (single-row table, id=1)                                 #
    # ------------------------------------------------------------------ #

    def get_user_state(self) -> dict:
        result = self.db.table("user_state").select("*").eq("id", 1).execute()
        if result.data:
            return result.data[0]
        default = {
            "id": 1,
            "assessment_done": False,
            "assessment_results": None,
            "current_chapter": 1,
            "email": "",
            "current_streak": 0,
            "longest_streak": 0,
            "last_session_date": None,
        }
        self.db.table("user_state").insert(default).execute()
        return default

    def update_settings(self, settings: dict):
        self.db.table("user_state").update(settings).eq("id", 1).execute()

    def reset_assessment(self):
        self.db.table("user_state").update({
            "assessment_done": False,
            "assessment_results": None,
        }).eq("id", 1).execute()

    # ------------------------------------------------------------------ #
    # Assessment                                                           #
    # ------------------------------------------------------------------ #

    def save_assessment_results(self, results: dict):
        self.db.table("user_state").update({
            "assessment_done": True,
            "assessment_results": results,
        }).eq("id", 1).execute()

        for category, score in results.get("category_scores", {}).items():
            wrong = max(0, int((1 - score / 100) * 10))
            self._upsert_error_category(category, total=10, new_wrong=wrong)

    # ------------------------------------------------------------------ #
    # Sessions                                                             #
    # ------------------------------------------------------------------ #

    def get_today_sessions(self) -> list[dict]:
        result = (
            self.db.table("sessions")
            .select("*")
            .eq("session_date", date.today().isoformat())
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def save_session(self, session: dict):
        row = {
            "session_date": date.today().isoformat(),
            "session_type": session["session_type"],
            "score": session["score"],
            "duration_minutes": max(1, session.get("duration_minutes", 1)),
            "errors": session.get("errors", []),
        }
        self.db.table("sessions").insert(row).execute()

        for error in session.get("errors", []):
            cat = error.get("category", "Egyéb")
            self._upsert_error_category(cat, total=1, new_wrong=1)

    def get_sessions_last_n_days(self, n: int = 14) -> list[dict]:
        since = (date.today() - timedelta(days=n)).isoformat()
        result = (
            self.db.table("sessions")
            .select("*")
            .gte("session_date", since)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    # ------------------------------------------------------------------ #
    # Streak                                                               #
    # ------------------------------------------------------------------ #

    def update_streak(self):
        state = self.get_user_state()
        today = date.today()
        last_raw = state.get("last_session_date")

        if last_raw:
            last = date.fromisoformat(last_raw) if isinstance(last_raw, str) else last_raw
            diff = (today - last).days
            if diff == 0:
                return  # already counted today
            new_streak = state.get("current_streak", 0) + 1 if diff == 1 else 1
        else:
            new_streak = 1

        longest = max(new_streak, state.get("longest_streak", 0))
        self.db.table("user_state").update({
            "current_streak": new_streak,
            "longest_streak": longest,
            "last_session_date": today.isoformat(),
        }).eq("id", 1).execute()

    # ------------------------------------------------------------------ #
    # Error categories                                                     #
    # ------------------------------------------------------------------ #

    def get_error_categories(self) -> dict[str, dict]:
        result = self.db.table("error_categories").select("*").execute()
        return {
            row["category"]: {
                "total": row["total_attempts"],
                "wrong": row["wrong_attempts"],
            }
            for row in (result.data or [])
        }

    def get_weakest_category(self) -> Optional[str]:
        cats = self.get_error_categories()
        if not cats:
            return None
        ranked = sorted(
            cats.items(),
            key=lambda x: x[1]["wrong"] / max(x[1]["total"], 1),
            reverse=True,
        )
        best = ranked[0]
        return best[0] if best[1]["wrong"] > 0 else None

    def _upsert_error_category(self, category: str, total: int, new_wrong: int):
        existing = (
            self.db.table("error_categories")
            .select("*")
            .eq("category", category)
            .execute()
        )
        if existing.data:
            cur = existing.data[0]
            self.db.table("error_categories").update({
                "total_attempts": cur["total_attempts"] + total,
                "wrong_attempts": cur["wrong_attempts"] + new_wrong,
                "last_updated": datetime.utcnow().isoformat(),
            }).eq("category", category).execute()
        else:
            self.db.table("error_categories").insert({
                "category": category,
                "total_attempts": total,
                "wrong_attempts": new_wrong,
                "last_updated": datetime.utcnow().isoformat(),
            }).execute()

    # ------------------------------------------------------------------ #
    # Vocabulary (spaced repetition, SM-2 variant)                        #
    # ------------------------------------------------------------------ #

    def add_vocabulary(self, word: dict):
        german = word.get("german", "").strip()
        if not german:
            return
        existing = (
            self.db.table("vocabulary")
            .select("id")
            .eq("german", german)
            .execute()
        )
        if not existing.data:
            self.db.table("vocabulary").insert({
                "german": german,
                "hungarian": word.get("hungarian", ""),
                "next_review": date.today().isoformat(),
                "ease_factor": 2.5,
                "interval_days": 1,
                "times_correct": 0,
                "times_wrong": 0,
            }).execute()

    def get_due_vocabulary(self, limit: int = 10) -> list[dict]:
        result = (
            self.db.table("vocabulary")
            .select("*")
            .lte("next_review", date.today().isoformat())
            .order("next_review")
            .limit(limit)
            .execute()
        )
        return result.data or []

    def update_vocabulary_review(self, word_id: str, correct: bool):
        result = self.db.table("vocabulary").select("*").eq("id", word_id).execute()
        if not result.data:
            return
        w = result.data[0]
        ease = w.get("ease_factor", 2.5)
        interval = w.get("interval_days", 1)

        if correct:
            new_interval = max(1, round(interval * ease))
            new_ease = min(3.0, ease + 0.1)
            times_correct = w.get("times_correct", 0) + 1
            times_wrong = w.get("times_wrong", 0)
        else:
            new_interval = 1
            new_ease = max(1.3, ease - 0.2)
            times_correct = w.get("times_correct", 0)
            times_wrong = w.get("times_wrong", 0) + 1

        next_review = (date.today() + timedelta(days=new_interval)).isoformat()
        self.db.table("vocabulary").update({
            "interval_days": new_interval,
            "ease_factor": round(new_ease, 2),
            "next_review": next_review,
            "times_correct": times_correct,
            "times_wrong": times_wrong,
        }).eq("id", word_id).execute()

    def get_vocabulary_stats(self) -> dict:
        result = self.db.table("vocabulary").select("*").execute()
        words = result.data or []
        due_today = sum(
            1 for w in words
            if w.get("next_review", "9999") <= date.today().isoformat()
        )
        return {
            "total": len(words),
            "due_today": due_today,
        }

    # ------------------------------------------------------------------ #
    # Setup helper (call once from a Python shell)                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def sql_setup() -> str:
        return """
-- Run this SQL once in the Supabase SQL Editor:

CREATE TABLE IF NOT EXISTS user_state (
    id          INTEGER PRIMARY KEY DEFAULT 1,
    assessment_done      BOOLEAN DEFAULT FALSE,
    assessment_results   JSONB,
    current_chapter      INTEGER DEFAULT 1,
    email                TEXT DEFAULT '',
    current_streak       INTEGER DEFAULT 0,
    longest_streak       INTEGER DEFAULT 0,
    last_session_date    DATE,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_date     DATE DEFAULT CURRENT_DATE,
    session_type     TEXT,
    score            INTEGER,
    duration_minutes INTEGER,
    errors           JSONB DEFAULT '[]',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_categories (
    category         TEXT PRIMARY KEY,
    total_attempts   INTEGER DEFAULT 0,
    wrong_attempts   INTEGER DEFAULT 0,
    last_updated     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vocabulary (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    german        TEXT NOT NULL UNIQUE,
    hungarian     TEXT DEFAULT '',
    next_review   DATE DEFAULT CURRENT_DATE,
    ease_factor   FLOAT DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    times_correct INTEGER DEFAULT 0,
    times_wrong   INTEGER DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
"""
