"""Full project diagnostics to find all issues."""
import sqlite3
from deprecio.core.fuzzy_search import calculate_match_score, normalize_search_text, extract_model_numbers

# ============================================================
# ISSUE 1: Brand normalization in DB (duplicate brands)
# ============================================================
print("=" * 60)
print("ISSUE 1: BRAND CASE DUPLICATES IN SQLite")
print("=" * 60)
conn = sqlite3.connect('data/global_devices.db')
cur = conn.cursor()
cur.execute("SELECT LOWER(brand), COUNT(DISTINCT brand), GROUP_CONCAT(DISTINCT brand) FROM phones GROUP BY LOWER(brand) HAVING COUNT(DISTINCT brand) > 1")
for row in cur.fetchall():
    print(f"  '{row[0]}' has {row[1]} variants: {row[2]}")

# ============================================================
# ISSUE 2: Missing POCO X6 (without Pro)  
# ============================================================
print()
print("=" * 60)
print("ISSUE 2: MISSING POCO X6 (non-Pro)")
print("=" * 60)
cur.execute("SELECT brand, name FROM phones WHERE LOWER(clean_name) LIKE '%poco x6%'")
results = cur.fetchall()
print(f"  Found {len(results)} POCO X6 records:", results)
print("  => POCO X6 (standard edition) is simply not in the dataset, only X6 Pro exists")

# ============================================================
# ISSUE 3: Redmi Note 13 plain version missing 
# ============================================================
print()
print("=" * 60)
print("ISSUE 3: REDMI NOTE 13 plain version")
print("=" * 60)
cur.execute("SELECT brand, name FROM phones WHERE LOWER(clean_name) LIKE '%redmi note 13%'")
results = cur.fetchall()
print(f"  Found {len(results)} records:")
for r in results:
    print(f"    {r}")
print("  => 'redmi note 13' query returns only Pro variants because dataset has no plain Redmi Note 13")

# ============================================================
# ISSUE 4: iQOO search - 'iqoo' not in KNOWN_BRANDS
# ============================================================
print()
print("=" * 60)
print("ISSUE 4: 'iqoo' not in KNOWN_BRANDS (cross-brand protection)")
print("=" * 60)
from deprecio.core.fuzzy_search import KNOWN_BRANDS
print(f"  'iqoo' in KNOWN_BRANDS: {'iqoo' in KNOWN_BRANDS}")
print("  => Querying 'iqoo 11' won't be blocked by brand check, but brand stored as 'Iqoo' not 'iQOO'")
print("  => The brand='Iqoo' in DB but clean_name starts with 'iqoo' so LIKE search works fine")

# ============================================================
# ISSUE 5: Year range/coverage for key modern brands
# ============================================================
print()
print("=" * 60)
print("ISSUE 5: MAX MODEL COVERAGE BY BRAND")
print("=" * 60)
for brand in ['Realme', 'vivo', 'Vivo', 'Iqoo', 'Poco', 'Xiaomi', 'OnePlus', 'Oneplus']:
    cur.execute("SELECT COUNT(*) FROM phones WHERE brand = ?", (brand,))
    cnt = cur.fetchone()[0]
    cur.execute("SELECT name FROM phones WHERE brand = ? ORDER BY name DESC LIMIT 3", (brand,))
    top = [r[0] for r in cur.fetchall()]
    print(f"  {brand}: {cnt} records | latest: {top}")

# ============================================================  
# ISSUE 6: GSMArena old dataset - max coverage year
# ============================================================
print()
print("=" * 60)
print("ISSUE 6: COVERAGE GAP - MODERN MODELS NOT IN DB")
print("=" * 60)
missing_models = [
    'Realme 12 Pro', 'Realme GT 6', 'Realme GT 6T',
    'vivo V30', 'vivo V40', 'iQOO 12', 'iQOO 13',
    'Poco X6', 'Poco F6',
    'Redmi Note 13', 'Redmi Note 14',
    'OnePlus 12R', 'OnePlus Nord 4',
]
for m in missing_models:
    norm = normalize_search_text(m)
    tokens = norm.split()
    clauses = " AND ".join(["clean_name LIKE ?" for _ in tokens])
    params = [f"%{t}%" for t in tokens]
    cur.execute(f"SELECT COUNT(*) FROM phones WHERE {clauses}", params)
    cnt = cur.fetchone()[0]
    status = "FOUND" if cnt > 0 else "MISSING"
    print(f"  [{status}] '{m}' ({cnt} match(es))")

conn.close()

# ============================================================
# ISSUE 7: _search_global_db silences all exceptions
# ============================================================
print()
print("=" * 60)
print("ISSUE 7: silent exception handling in _search_global_db")
print("=" * 60)
print("  cached_provider.py line 172: 'except Exception: return []'")
print("  => Any parse error causes silent empty result, no logging")

# ============================================================
# ISSUE 8: MSRP estimation is always a hardcoded heuristic
# ============================================================
print()
print("=" * 60)
print("ISSUE 8: MSRP ESTIMATION ACCURACY")
print("=" * 60)
print("  gsmarena_parser.py _parse_memory_variants() heuristic:")
print("  <= 2019: 14000 + (storage/64)*4000")
print("  <= 2021: 25000 + (storage/128)*10000")
print("  else:    40000 + (storage/256)*25000")
print("  => No brand-specific pricing: Xiaomi 128GB != Samsung 128GB at same year")
print("  => No tier weighting: flagship vs midrange gets same formula")

# ============================================================
# ISSUE 9: _estimate_tier is too simplistic
# ============================================================
print()
print("=" * 60)
print("ISSUE 9: TIER ESTIMATION GAPS")
print("=" * 60)
from deprecio.providers.gsmarena_parser import GSMArenaParser
test_names = [
    ('iQOO 11 Pro 5G', 'Expected: Ultra-Flagship'),
    ('vivo X90 Pro Plus 5G', 'Expected: Ultra-Flagship'),
    ('Realme GT 6', 'Expected: Flagship'),
    ('Realme C55', 'Expected: Budget'),
    ('Poco X6 Pro 5G', 'Expected: Sub-flagship'),
    ('Redmi A3', 'Expected: Budget'),
    ('Galaxy S24 FE', 'Expected: Sub-flagship'),
]
for name, expected in test_names:
    tier = GSMArenaParser._estimate_tier(name)
    print(f"  '{name}': got='{tier}' | {expected}")

# ============================================================
# ISSUE 10: Duplicate model IDs in DB from different data sources
# ============================================================
print()
print("=" * 60)
print("ISSUE 10: POTENTIAL SLUG COLLISIONS")
print("=" * 60)
conn = sqlite3.connect('data/global_devices.db')
cur = conn.cursor()
cur.execute("SELECT id, COUNT(*) as cnt FROM phones GROUP BY id HAVING cnt > 1")
dupes = cur.fetchall()
print(f"  Duplicate IDs: {len(dupes)}")
if dupes:
    for d in dupes[:5]:
        print(f"    {d}")
conn.close()
