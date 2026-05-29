# Bia Államvizsga Segéd – Setup & Deploy

## 1. Supabase (opcionális – app nélküle is fut, csak lokálisan tárolja az adatokat)

1. Regisztrálj: [supabase.com](https://supabase.com) (ingyenes tier elég)
2. Hozz létre új projektet
3. **SQL Editor → New query** → futtasd ezt:

```sql
create table tetel_confidence (
  tetel_id integer primary key,
  weight integer not null default 3,
  last_practiced date,
  practice_count integer default 0
);

create table sessions (
  id bigserial primary key,
  tetel_id integer not null,
  session_type text not null,
  score integer,
  duration_minutes integer,
  created_at timestamptz default now()
);
```

4. **Settings → API** → másold ki:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_KEY`

---

## 2. Streamlit Cloud – deploy

1. Menj: [share.streamlit.io](https://share.streamlit.io)
2. **New app** → válaszd:
   - **Repository:** `nyasika/AI-agents`
   - **Branch:** `main`
   - **Main file path:** `agents/Personal/2_Bia-allamvizsga-agent/app.py`
3. **Advanced settings → Secrets** – add meg TOML formátumban:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."

# Supabase (opcionális)
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."
```

4. **Deploy** → az app elérhető lesz a Streamlit Cloud URL-jén

---

## 3. Lokális futtatás

```bash
cd agents/Personal/2_Bia-allamvizsga-agent

# .env fájl létrehozása
cp .env.example .env
# szerkeszd valódi értékekkel

pip install -r requirements.txt
streamlit run app.py
```

---

## Megjegyzések

- A `data/tetelek/` mappa (30 JSON + 660 PNG, ~127 MB) a repóban van — deploy-kor automatikusan elérhető
- A preprocessing (`preprocessing/ingest.py`) egyszeri lokális futtatás volt, Streamlit Cloud-on nem kell futtatni
- Supabase nélkül az app session-szintű local state-ben tárolja a confidence adatokat (oldal újratöltéskor elvész)
