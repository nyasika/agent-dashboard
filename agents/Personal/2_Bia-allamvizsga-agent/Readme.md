# Bia Államvizsga Segéd

**Live app:** https://nyasikaallamvizsgaapp.streamlit.app

Biológia szóbeli államvizsga felkészítő AI agent — Pécsi Egyetem, 30 tétel.

---

## Funkciók

- **Tétel áttekintés** — összefoglaló, kulcsfogalmak, képek
- **Fogalom drill** — 5 definíciós kérdés AI értékeléssel
- **Vizsgaszimulátor** — 5 szóbeli vizsgakérdés, kvalitatív visszajelzés
- **Confidence tracking** — 4 fokozatú visszajelzés, súlyozott véletlenhúzás
- **Statisztika** — haladás, gyenge tételek kiemelése

---

## Adatok

- 30 tétel feldolgozva Word fájlokból
- 660 kép (PNG) a tételekből
- Supabase: confidence + session tracking

---

## Deployment

- **Repo:** `nyasika/agent-dashboard` (public)
- **Main file:** `agents/Personal/2_Bia-allamvizsga-agent/app.py`
- **Secrets:** `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`

Részletes setup: [SETUP.md](SETUP.md)

---

## Lokális futtatás

```bash
cd agents/Personal/2_Bia-allamvizsga-agent
pip install -r requirements.txt
streamlit run app.py
```
