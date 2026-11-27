"""Builder script to construct the Global GSMArena Offline SQLite Database for Deprecio."""

import csv
import io
import json
import os
import sqlite3
import time
import argparse
from pathlib import Path
import httpx
from deprecio.core.fuzzy_search import normalize_search_text

BRANDS_URL = "https://raw.githubusercontent.com/ilyasozkurt/mobilephone-brands-and-models/master/brands.json"
DEVICES_URL = "https://raw.githubusercontent.com/ilyasozkurt/mobilephone-brands-and-models/master/devices.json"
MODERN_URL = "https://huggingface.co/datasets/jason1966/abhijitdahatonde_real-world-smartphones-dataset/raw/main/smartphones.csv"



# Словарь нормализации брендов, чтобы избежать дублей (vivo vs Vivo)
BRAND_MAP = {
    "vivo": "vivo", "iqoo": "iQOO", "poco": "POCO", "realme": "Realme",
    "oneplus": "OnePlus", "xiaomi": "Xiaomi", "redmi": "Redmi",
    "oppo": "OPPO", "honor": "Honor", "huawei": "Huawei", "apple": "Apple",
    "samsung": "Samsung", "zte": "ZTE", "lg": "LG", "tcl": "TCL", "blu": "BLU",
    "motorola": "Motorola", "nokia": "Nokia", "asus": "Asus", "meizu": "Meizu",
    "infinix": "Infinix", "tecno": "Tecno", "google": "Google", "nothing": "Nothing"
}

def normalize_brand(b: str) -> str:
    b_lower = b.lower().strip()
    return BRAND_MAP.get(b_lower, b.title())

def build_global_db(dest_path: Path, catalog_path: Path = Path("data/catalog.json")) -> None:
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
        brands = {b["id"]: normalize_brand(b["name"]) for b in brands_data.get("RECORDS", [])}

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
        modern_items = []
        try:
            r_modern = client.get(MODERN_URL)
            if r_modern.status_code == 200:
                clean_csv = r_modern.text.lstrip("\ufeff")
                reader = csv.DictReader(io.StringIO(clean_csv))
                modern_items.extend(list(reader))
        except Exception as e:
            print(f"[!] Не удалось загрузить внешний датасет современных устройств: {e}")

        supplement_path = Path("data/modern_supplement.json")
        if supplement_path.exists():
            print("[*] Загрузка локального дополнения современных моделей...")
            try:
                with open(supplement_path, "r", encoding="utf-8") as f:
                    supplement_items = json.load(f)
                    modern_items.extend(supplement_items)
            except Exception as e:
                print(f"[!] Ошибка загрузки supplement: {e}")

        modern_count = 0
        for item in modern_items:
            model_name = item.get("model", "").strip()
            brand_name = normalize_brand(item.get("brand_name", ""))
            if not model_name or model_name.lower() in seen_names:
                continue

            slug_id = f"mod-{model_name.lower().replace(' ', '-')}"
            clean_name = normalize_search_text(f"{brand_name} {model_name}" if brand_name.lower() not in model_name.lower() else model_name)
            chipset = item.get("processor_brand", "")
            ram = item.get("ram_capacity", "")
            storage = item.get("internal_memory", "")
            battery = item.get("battery_capacity", "")
            has_5g = str(item.get("5G_or_not", "")) == "1"

            specs_dict = {
                "Chipset": chipset,
                "Internal": f"{storage}GB {ram}GB RAM" if storage and ram else "",
                "Battery": f"{battery} mAh" if battery else "",
                "4G bands": "1, 3, 7, 20, 38, 40 (Global)",
                "5G bands": "n1, n3, n7, n20, n77, n78" if has_5g else "",
                "SIM": "Nano-SIM and eSIM" if has_5g else "Dual SIM",
                "Status": "Available. Released 2023-2024",
            }

            seen_names.add(model_name.lower())
            rows.append((
                slug_id,
                brand_name,
                model_name,
                clean_name,
                "Released 2023-2024",
                chipset,
                json.dumps(specs_dict, ensure_ascii=False),
            ))
            modern_count += 1
        print(f"[+] Добавлено {modern_count} уникальных современных моделей!")

    if catalog_path.exists():
        print(f"[*] Добавление избранного каталога из {catalog_path}...")
        catalog_records = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(catalog_records, list):
            raise ValueError("catalog root must be a list")
        for item in catalog_records:
            if not isinstance(item, dict) or not all(item.get(key) for key in ("model_id", "brand", "name")):
                raise ValueError("catalog records must contain model_id, brand and name")
            clean_name = normalize_search_text(f"{item['brand']} {item['name']}")
            rows.append((
                item["model_id"], item["brand"], item["name"], clean_name,
                str(item.get("editions", [{}])[0].get("release_date") or ""),
                item.get("chipset") or "", json.dumps(item, ensure_ascii=False),
            ))

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

    # Создание FTS5 виртуальной таблицы для быстрого полнотекстового поиска
    cur.execute(
        """
        CREATE VIRTUAL TABLE phones_fts USING fts5(
            id UNINDEXED,
            brand,
            name,
            clean_name,
            content=phones,
            content_rowid=rowid
        )
        """
    )
    cur.execute("INSERT INTO phones_fts(phones_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

    os.replace(tmp_path, dest_path)

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    print(f"[+] База успешно создана за {time.time() - t0:.2f} сек. Записей: {len(rows)}, Размер: {size_mb:.2f} МБ")


def build_catalog_db(catalog_path: Path, dest_path: Path) -> None:
    """Build the local SQLite catalog deterministically from catalog.json."""
    records = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or any(
        not isinstance(item, dict) or not all(item.get(key) for key in ("model_id", "brand", "name"))
        for item in records
    ):
        raise ValueError("catalog must be a list of records with model_id, brand and name")
    ids = [item["model_id"] for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog contains duplicate model_id values")
    rows = []
    for item in records:
        rows.append((
            item["model_id"], item["brand"], item["name"],
            normalize_search_text(f"{item['brand']} {item['name']}"),
            str(item.get("editions", [{}])[0].get("release_date") or ""),
            item.get("chipset") or "", json.dumps(item, ensure_ascii=False),
        ))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(".tmp.db")
    if tmp_path.exists():
        tmp_path.unlink()
    conn = sqlite3.connect(tmp_path)
    try:
        conn.execute("CREATE TABLE phones (id TEXT PRIMARY KEY, brand TEXT, name TEXT, clean_name TEXT, released_at TEXT, chipset TEXT, raw_specs TEXT)")
        conn.execute("CREATE INDEX idx_phones_clean_name ON phones(clean_name)")
        conn.execute("CREATE INDEX idx_phones_brand ON phones(brand)")
        conn.executemany("INSERT INTO phones VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        conn.execute("CREATE VIRTUAL TABLE phones_fts USING fts5(id UNINDEXED, brand, name, clean_name, content=phones, content_rowid=rowid)")
        conn.execute("INSERT INTO phones_fts(phones_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(tmp_path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if result != "ok":
        tmp_path.unlink(missing_ok=True)
        raise sqlite3.DatabaseError(f"catalog database integrity check failed: {result}")
    os.replace(tmp_path, dest_path)
    print(f"[+] Каталог собран из {catalog_path}: {len(rows)} записей в {dest_path}")


def merge_catalog_db(catalog_path: Path, database_path: Path) -> None:
    """Add canonical catalog records to an existing global database atomically."""
    records = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or any(
        not isinstance(item, dict) or not all(item.get(key) for key in ("model_id", "brand", "name"))
        for item in records
    ):
        raise ValueError("catalog must be a list of records with model_id, brand and name")
    ids = [item["model_id"] for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog contains duplicate model_id values")
    if not database_path.exists():
        raise FileNotFoundError(database_path)

    tmp_path = database_path.with_suffix(".tmp.db")
    tmp_path.unlink(missing_ok=True)
    source = sqlite3.connect(database_path)
    target = sqlite3.connect(tmp_path)
    try:
        source.backup(target)
    finally:
        source.close()
    try:
        target.executemany(
            "INSERT OR REPLACE INTO phones (id, brand, name, clean_name, released_at, chipset, raw_specs) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(
                item["model_id"], item["brand"], item["name"],
                normalize_search_text(f"{item['brand']} {item['name']}"),
                str(item.get("editions", [{}])[0].get("release_date") or ""),
                item.get("chipset") or "", json.dumps(item, ensure_ascii=False),
            ) for item in records],
        )
        target.execute("INSERT INTO phones_fts(phones_fts) VALUES('rebuild')")
        target.commit()
        result = target.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"database integrity check failed: {result}")
    except Exception:
        target.close()
        tmp_path.unlink(missing_ok=True)
        raise
    target.close()
    os.replace(tmp_path, database_path)
    print(f"[+] Добавлено/обновлено {len(records)} curated-моделей в {database_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, help="Build from local catalog.json instead of remote datasets")
    parser.add_argument("--merge-catalog", type=Path, help="Merge a curated catalog into an existing database")
    parser.add_argument("--output", type=Path, default=Path("data/global_devices.db"))
    args = parser.parse_args()
    if args.merge_catalog:
        merge_catalog_db(args.merge_catalog, args.output)
    elif args.catalog:
        build_catalog_db(args.catalog, args.output)
    else:
        build_global_db(args.output)
