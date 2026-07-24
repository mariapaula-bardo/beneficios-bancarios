"""Corre los dos scrapers, guarda data/beneficios.json y genera el sitio."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrape_bancochile import scrape as scrape_bancochile
from scrape_santander import scrape as scrape_santander
from build_site import build

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


def main():
    beneficios = []

    try:
        beneficios += scrape_bancochile()
    except Exception as e:
        print(f"[WARN] Falló scraper Banco de Chile: {e}", file=sys.stderr)

    try:
        beneficios += scrape_santander()
    except Exception as e:
        print(f"[WARN] Falló scraper Santander: {e}", file=sys.stderr)

    output = {
        "actualizado": datetime.now().isoformat(timespec="minutes"),
        "beneficios": beneficios,
    }

    with open(DATA_DIR / "beneficios.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Guardados {len(beneficios)} beneficios en data/beneficios.json")

    build(output)
    print("Sitio generado en site/")


if __name__ == "__main__":
    main()
