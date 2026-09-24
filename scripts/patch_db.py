import re

with open('scripts/build_global_db.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_code = '''
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

'''

if 'BRAND_MAP = {' not in code:
    code = code.replace('def build_global_db(dest_path: Path) -> None:', new_code + 'def build_global_db(dest_path: Path) -> None:')
    code = code.replace('brands = {b["id"]: b["name"] for b in brands_data.get("RECORDS", [])}', 'brands = {b["id"]: normalize_brand(b["name"]) for b in brands_data.get("RECORDS", [])}')

old_modern = '''        try:
            r_modern = client.get(MODERN_URL)
            if r_modern.status_code == 200:
                clean_csv = r_modern.text.lstrip("\\ufeff")
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
            print(f"[!] Не удалось загрузить датасет современных устройств: {e}")'''


new_modern = '''        modern_items = []
        try:
            r_modern = client.get(MODERN_URL)
            if r_modern.status_code == 200:
                clean_csv = r_modern.text.lstrip("\\ufeff")
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
        print(f"[+] Добавлено {modern_count} уникальных современных моделей!")'''

code = code.replace(old_modern, new_modern)

with open('scripts/build_global_db.py', 'w', encoding='utf-8') as f:
    f.write(code)
