"""
Preprocessing pipeline: Tetelek/*.doc(x) -> data/tetelek/tetel_XX.json + PNG kepek

Futtatás a projekt gyökeréből:
    python preprocessing/ingest.py

Egyszeri futtatás. Mar feldolgozott teteleket kihagyja (--force-vel ujrafut).
Szükséges: LibreOffice (soffice) a PATH-ban vagy alapértelmezett helyen.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from PIL import Image

# Windows terminal UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ------------------------------------------------------------------ #
# Útvonalak                                                            #
# ------------------------------------------------------------------ #

PROJECT_ROOT = Path(__file__).parent.parent
TETELEK_DIR  = PROJECT_ROOT / "Tetelek"
DATA_DIR     = PROJECT_ROOT / "data" / "tetelek"
IMAGES_DIR   = DATA_DIR / "images"

SOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "soffice",
]

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

load_dotenv(PROJECT_ROOT / ".env")
client = anthropic.Anthropic()


def find_soffice() -> str:
    for p in SOFFICE_PATHS:
        if p != "soffice":
            if Path(p).exists():
                return p
        else:
            try:
                subprocess.run([p, "--version"], capture_output=True, timeout=10, check=True)
                return p
            except Exception:
                continue
    raise RuntimeError(
        "LibreOffice (soffice) nem található. "
        "Telepítsd: winget install TheDocumentFoundation.LibreOffice"
    )


def doc_to_docx(doc_path: Path, soffice: str, out_dir: Path) -> Path:
    """Konvertálja a .doc fájlt .docx-re LibreOffice segítségével."""
    subprocess.run(
        [soffice, "--headless", "--convert-to", "docx",
         str(doc_path), "--outdir", str(out_dir)],
        capture_output=True, timeout=60, check=True
    )
    docx_path = out_dir / doc_path.with_suffix(".docx").name
    if not docx_path.exists():
        raise FileNotFoundError(f"Konverzió sikertelen: {doc_path.name}")
    return docx_path


def parse_filename(filename: str) -> tuple[int, str]:
    """'3 - Cím.doc' → (3, 'Cím')"""
    name = Path(filename).stem
    m = re.match(r"^(\d+)\s*[-–]\s*(.+)$", name)
    if m:
        tetel_id = int(m.group(1))
        cim = m.group(2).replace("-", " ").strip()
        return tetel_id, cim
    raise ValueError(f"Nem ismert fájlnév: {filename}")


def extract_text_from_docx(docx_path: Path) -> str:
    """Szöveg kinyerése python-docx nélkül (zipfile + XML parsing)."""
    import xml.etree.ElementTree as ET

    NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []

    with zipfile.ZipFile(docx_path) as z:
        if "word/document.xml" not in z.namelist():
            return ""
        xml = z.read("word/document.xml")

    root = ET.fromstring(xml)
    for para in root.iter(f"{NS}p"):
        texts = [r.text or "" for r in para.iter(f"{NS}t")]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)

    return "\n".join(paragraphs)


def extract_images_from_docx(docx_path: Path, tetel_id: int) -> list[dict]:
    """Képek kimentése PNG-be; visszaadja a metaadatokat Vision leírás nélkül."""
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".emf", ".wmf"}
    result = []

    with zipfile.ZipFile(docx_path) as z:
        media = [f for f in z.namelist()
                 if f.startswith("word/media/")
                 and Path(f).suffix.lower() in IMAGE_EXTS]

        for i, media_file in enumerate(media, 1):
            raw = z.read(media_file)
            ext = Path(media_file).suffix.lower()
            out_path = IMAGES_DIR / f"tetel_{tetel_id:02d}_img_{i}.png"

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(raw)
                tmp_name = tmp.name

            try:
                img = Image.open(tmp_name).convert("RGB")
                img.save(out_path, "PNG")
                result.append({
                    "sorszam": i,
                    "fajl": str(out_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "vision_leiras": "",
                    "szovegkornyezet": "",
                })
            except Exception as e:
                print(f"    ⚠  Kép kihagyva ({media_file}): {e}")
            finally:
                os.unlink(tmp_name)

    return result


def vision_describe(img_path: Path) -> str:
    """Claude Vision leírás generálása egy képhez."""
    with open(img_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        "Ez egy biológia államvizsga tételből származó ábra. "
                        "Írj részletes, pontos magyar nyelvű leírást! "
                        "Minden feliratot, struktúrát, folyamatot és összefüggést írj le. "
                        "A leírást biológia szakos hallgató használja felkészüléshez."
                    ),
                },
            ],
        }],
    )
    return resp.content[0].text


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


def generate_summary_and_concepts(szoveg: str, cim: str) -> dict:
    """Összefoglaló + kulcsfogalmak Claude-dal."""
    prompt = f"""Biológia témakör: {cim}

Szöveg (első 6000 karakter):
{szoveg[:6000]}

Adj vissza CSAK ezt a JSON struktúrát, semmi mást:
{{
  "kulcsfogalmak": ["fogalom1", "fogalom2", "fogalom3"],
  "osszefoglalo": "3-5 mondatos összefoglaló magyarul, ami az államvizsga szempontjából legfontosabb pontokat tartalmazza."
}}"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return _extract_json(resp.content[0].text)
    except Exception:
        return {"kulcsfogalmak": [], "osszefoglalo": ""}


# ------------------------------------------------------------------ #
# Fő pipeline                                                          #
# ------------------------------------------------------------------ #

def process_tetel(doc_path: Path, soffice: str, force: bool) -> None:
    tetel_id, cim = parse_filename(doc_path.name)
    out_json = DATA_DIR / f"tetel_{tetel_id:02d}.json"

    if out_json.exists() and not force:
        print(f"  ⏭  Tétel {tetel_id:02d} már feldolgozva, kihagyva (--force-vel újrafut)")
        return

    print(f"\n{'='*60}")
    print(f"  Tétel {tetel_id:02d}: {cim}")
    print(f"{'='*60}")

    # 1. .doc → .docx konverzió ha szükséges (temp mappába, nem a forrás mellé)
    temp_dir = None
    temp_docx = None
    if doc_path.suffix.lower() == ".doc":
        print("  → .doc konvertálása .docx-re (LibreOffice)...")
        import shutil
        temp_dir = Path(tempfile.mkdtemp())
        docx_path = doc_to_docx(doc_path, soffice, temp_dir)
        temp_docx = docx_path
    else:
        docx_path = doc_path

    try:
        # 2. Szöveg kinyerése
        print("  → Szöveg kinyerése...")
        szoveg = extract_text_from_docx(docx_path)
        print(f"     {len(szoveg)} karakter")

        # 3. Képek kinyerése
        print("  → Képek kinyerése...")
        kepek = extract_images_from_docx(docx_path, tetel_id)
        print(f"     {len(kepek)} kép találva")

        # 4. Összefoglaló + kulcsfogalmak
        print("  → Összefoglaló + kulcsfogalmak generálása...")
        meta = generate_summary_and_concepts(szoveg, cim)

        # 5. JSON mentés
        tetel = {
            "id": tetel_id,
            "cim": cim,
            "szoveg": szoveg,
            "kepek": kepek,
            "kulcsfogalmak": meta.get("kulcsfogalmak", []),
            "osszefoglalo": meta.get("osszefoglalo", ""),
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(tetel, f, ensure_ascii=False, indent=2)

        print(f"  ✅ Kész → {out_json.name}")

    finally:
        if temp_dir and temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)


def main():
    parser = argparse.ArgumentParser(description="Tetelek Word fájlok → JSON + PNG")
    parser.add_argument("--force", action="store_true",
                        help="Már feldolgozott tételek újrafuttatása")
    parser.add_argument("--tetel", type=int, default=None,
                        help="Csak egy adott tételszámot dolgoz fel (pl. --tetel 3)")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("LibreOffice keresése...")
    soffice = find_soffice()
    print(f"  ✅ {soffice}")

    doc_files = sorted(
        list(TETELEK_DIR.glob("*.doc")) + list(TETELEK_DIR.glob("*.docx")),
        key=lambda p: parse_filename(p.name)[0]
    )

    # Szűrés adott tételre
    if args.tetel:
        doc_files = [f for f in doc_files
                     if parse_filename(f.name)[0] == args.tetel]
        if not doc_files:
            print(f"Nem található a(z) {args.tetel}. tétel.")
            return

    print(f"\n{len(doc_files)} fájl feldolgozása...\n")

    errors = []
    for doc_path in doc_files:
        try:
            process_tetel(doc_path, soffice, args.force)
        except Exception as e:
            print(f"  ❌ HIBA: {doc_path.name}: {e}")
            errors.append((doc_path.name, str(e)))

    print(f"\n{'='*60}")
    print(f"Feldolgozás kész. {len(doc_files) - len(errors)}/{len(doc_files)} sikeres.")
    if errors:
        print("\nHibás fájlok:")
        for name, err in errors:
            print(f"  ❌ {name}: {err}")


if __name__ == "__main__":
    main()
