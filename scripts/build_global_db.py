"""Builder script to construct the Global GSMArena Offline SQLite Database for Deprecio."""

import csv
import io
import json
import os
import sqlite3
import time
from pathlib import Path
import httpx
from deprecio.core.fuzzy_search import normalize_search_text

BRANDS_URL = "https://raw.githubusercontent.com/ilyasozkurt/mobilephone-brands-and-models/master/brands.json"
DEVICES_URL = "https://raw.githubusercontent.com/ilyasozkurt/mobilephone-brands-and-models/master/devices.json"
MODERN_URL = "https://huggingface.co/datasets/jason1966/abhijitdahatonde_real-world-smartphones-dataset/raw/main/smartphones.csv"


def build_global_db(dest_path: Path) -> None:
    """Загружает датасеты GSMArena + современные устройства (2021-2024) и формирует SQLite базу."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(".tmp.db")
    if tmp_path.exists():
        tmp_path.unlink()

    print(f"[*] Сборка глобальной базы смартфонов в {dest_path}...")
    t0 = time.time()

    rows = []
    seen_names = set()

    with httpx.Client(timeout=45.0) as client:
        # 1. Загрузка классической базы GSMArena (10 633 устройства)
        print("[*] Загрузка списка брендов GSMArena...")
        r_brands = client.get(BRANDS_URL)
        r_brands.raise_for_status()
        brands_data = r_brands.json()
        brands = {b["id"]: b["name"] for b in brands_data.get("RECORDS", [])}

        print("[*] Загрузка 10 600+ устройств GSMArena...")
        r_devs = client.get(DEVICES_URL)
        r_devs.raise_for_status()
        devices_data = r_devs.json()
        records = devices_data.get("RECORDS", [])

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
            seen_names.add(name.lower())
            rows.append((dev_id, brand, name, clean_name, released_at, chipset, raw_specs))

        # 2. Загрузка современных смартфонов 2021-2024 годов (OnePlus 11, Redmi Note 12, Pixel 6/7, Poco F5/X6 и др.)
        print("[*] Загрузка современных устройств 2021-2024 годов...")
        try:
            r_modern = client.get(MODERN_URL)
            if r_modern.status_code == 200:
                clean_csv = r_modern.text.lstrip("\ufeff")
                reader = csv.DictReader(io.StringIO(clean_csv))
                modern_count = 0
                for item in reader:
                    model_name = item.get("model", "").strip()
                    brand_name = item.get("brand_name", "").strip().capitalize()
                    if not model_name or model_name.lower() in seen_names:
                        continue

                    # Формируем slug ID
                    slug_id = f"mod-{model_name.lower().replace(' ', '-')}"
                    clean_name = normalize_search_text(f"{brand_name} {model_name}" if brand_name.lower() not in model_name.lower() else model_name)
                    chipset = item.get("processor_brand", "")
                    ram = item.get("ram_capacity", "")
                    storage = item.get("internal_memory", "")
                    battery = item.get("battery_capacity", "")
                    has_5g = item.get("5G_or_not") == "1"

                    specs_dict = {
                        "Chipset": chipset,
                        "Internal": f"{storage}GB {ram}GB RAM" if storage and ram else "",
                        "Battery": f"{battery} mAh" if battery else "",
                        "4G bands": "1, 3, 7, 20, 38, 40 (Global)",
                        "5G bands": "n1, n3, n7, n20, n77, n78" if has_5g else "",
                        "SIM": "Nano-SIM and eSIM" if has_5g else "Dual SIM",
                        "NFC": "Yes",
                        "Status": "Available. Released 2022-2024",
                    }

                    seen_names.add(model_name.lower())
                    rows.append((
                        slug_id,
                        brand_name,
                        model_name,
                        clean_name,
                        "Released 2023",
                        chipset,
                        json.dumps(specs_dict, ensure_ascii=False),
                    ))
                    modern_count += 1
                print(f"[+] Добавлено {modern_count} уникальных современных моделей!")
        except Exception as e:
            print(f"[!] Не удалось загрузить датасет современных устройств: {e}")

    print(f"[*] Всего {len(rows)} записей. Индексация в SQLite...")
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
