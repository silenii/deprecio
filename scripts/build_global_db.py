"""Builder script to construct the Global GSMArena Offline SQLite Database for Deprecio."""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
import httpx
from deprecio.core.fuzzy_search import normalize_search_text

BRANDS_URL = "https://raw.githubusercontent.com/ilyasozkurt/mobilephone-brands-and-models/master/brands.json"
DEVICES_URL = "https://raw.githubusercontent.com/ilyasozkurt/mobilephone-brands-and-models/master/devices.json"


def build_global_db(dest_path: Path) -> None:
    """Загружает датасет GSMArena и формирует оптимизированную базу SQLite."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(".tmp.db")
    if tmp_path.exists():
        tmp_path.unlink()

    print(f"[*] Сборка глобальной базы смартфонов в {dest_path}...")
    t0 = time.time()

    print("[*] Загрузка списка брендов...")
    with httpx.Client(timeout=30.0) as client:
        r_brands = client.get(BRANDS_URL)
        r_brands.raise_for_status()
        brands_data = r_brands.json()
        brands = {b["id"]: b["name"] for b in brands_data.get("RECORDS", [])}

        print("[*] Загрузка 10 600+ устройств GSMArena...")
        r_devs = client.get(DEVICES_URL)
        r_devs.raise_for_status()
        devices_data = r_devs.json()
        records = devices_data.get("RECORDS", [])

    print(f"[*] Получено {len(records)} записей. Индексация в SQLite...")
    conn = sqlite3.connect(tmp_path)
    cur = conn.cursor()

    cur.execute("PRAGMA synchronous = OFF")
    cur.execute("PRAGMA journal_mode = MEMORY")

    cur.execute(
        """
        CREATE TABLE phones (
            id TEXT PRIMARY KEY,
            brand TEXT,
            name TEXT,
            clean_name TEXT,
            released_at TEXT,
            chipset TEXT,
            raw_specs TEXT
        )
        """
    )
    cur.execute("CREATE INDEX idx_phones_clean_name ON phones(clean_name)")
    cur.execute("CREATE INDEX idx_phones_brand ON phones(brand)")

    rows = []
    for r in records:
        dev_id = str(r.get("id"))
        brand = brands.get(r.get("brand_id", ""), "")
        name = r.get("name", "").strip()
        if not name:
            continue
        clean_name = normalize_search_text(f"{brand} {name}" if brand and brand.lower() not in name.lower() else name)
        released_at = r.get("released_at", "")
        chipset = r.get("chipset", "")
        raw_specs = r.get("specifications", "{}")
        rows.append((dev_id, brand, name, clean_name, released_at, chipset, raw_specs))

    cur.executemany("INSERT OR REPLACE INTO phones VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()

    if dest_path.exists():
        dest_path.unlink()
    tmp_path.rename(dest_path)

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    print(f"[+] База успешно создана за {time.time() - t0:.2f} сек. Записей: {len(rows)}, Размер: {size_mb:.2f} МБ")


if __name__ == "__main__":
    target = Path("data/global_devices.db")
    build_global_db(target)
