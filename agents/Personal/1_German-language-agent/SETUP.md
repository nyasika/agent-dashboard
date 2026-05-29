# Deutsch Üben – Setup Guide

## 1. Supabase – adatbázis létrehozása

1. Regisztrálj a [supabase.com](https://supabase.com) oldalon (ingyenes tier elég)
2. Hozz létre egy új projektet
3. Nyisd meg: **SQL Editor** → **New query**
4. Futtasd ezt a Python kódot egyszer lokálisan a séma lekéréséhez:
   ```python
   from database import Database
   print(Database.sql_setup())
   ```
5. Másold be a kimenetet az SQL editorba, és futtasd
6. A projekt beállításaiban (**Settings → API**) másold ki:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_KEY`

---

## 2. Gmail App Password – emlékeztető emailekhez

1. Menj a Google Fiókodba → **Biztonság**
2. Kapcsold be a **2 lépéses hitelesítést** (ha még nincs)
3. Keresőbe írd: "App jelszavak" (vagy: myaccount.google.com/apppasswords)
4. Alkalmazás: "Mail", Eszköz: "Other (Custom name)" → pl. "Deutsch Agent"
5. A kapott **16 karakteres jelszót** (4×4 betű, szóközzel) másold a `GMAIL_APP_PASSWORD`-be

---

## 3. Streamlit Cloud – deploy

1. Töltsd fel a `german-agent/` mappát egy GitHub repóba
2. Menj a [share.streamlit.io](https://share.streamlit.io) oldalra
3. **New app** → válaszd ki a repót, branch: `main`, fájl: `app.py`
4. **Advanced settings → Secrets** – másold be (TOML formátumban):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."
GMAIL_USER = "yourname@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
APP_URL = "https://your-app.streamlit.app"
REMINDER_TOKEN = "valami-titkos-token-123"
```

5. Deploy → az app URL-je lesz az `APP_URL` értéke

---

## 4. cron-job.org – napi emlékeztetők

1. Regisztrálj a [cron-job.org](https://cron-job.org) oldalon (ingyenes)
2. **Create cronjob** × 2 (reggel + este):

   - **URL**: `https://your-app.streamlit.app/?action=remind&token=valami-titkos-token-123`
   - **Schedule**: pl. `0 7 * * *` (reggel 7:00) és `0 19 * * *` (este 19:00)
   - **Method**: GET

3. A `token` értéknek pontosan egyeznie kell a `REMINDER_TOKEN` secret-tel

---

## 5. Lokális futtatás (fejlesztéshez)

```bash
# .env fájl létrehozása (a .env.example alapján)
cp .env.example .env
# szerkeszd a .env-t valódi értékekkel

pip install -r requirements.txt
streamlit run app.py
```

---

## Fájlstruktúra

```
german-agent/
├── app.py           # Streamlit frontend + cron endpoint
├── agent.py         # Claude API hívások
├── database.py      # Supabase műveletek
├── reminder.py      # Gmail SMTP emailküldés
├── curriculum.py    # Tananyag (fejezetek, grammatika)
├── requirements.txt
├── .env.example
└── SETUP.md
```
