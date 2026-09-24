"""Comprehensive test to find all search and logic bugs."""
import sys
sys.path.insert(0, '.')

from deprecio.core.fuzzy_search import calculate_match_score, normalize_search_text, check_brand_compatibility
from deprecio.providers.cached_provider import CachedSpecsProvider

catalog = CachedSpecsProvider()

test_queries = [
    "realme gt",
    "realme gt 2 pro",
    "vivo v27",
    "iqoo 11",
    "iqoo neo 7",
    "vivo iqoo",
    "vivo x90",
    "iphone 15",
    "galaxy s24",
    "poco x6",
    "redmi note 13",
    "oneplus 12",
]

print("=== SEARCH DIAGNOSTICS ===\n")
for q in test_queries:
    results = catalog.search_devices(q)
    if results:
        top = results[:3]
        print(f"QUERY: '{q}'  => FOUND {len(results)} results")
        for d in top:
            print(f"  - {d.name} [{d.brand}]")
    else:
        print(f"QUERY: '{q}'  => *** NOT FOUND ***")
    print()

print("\n=== SCORE DIAGNOSTICS FOR PROBLEM CASES ===")
cases = [
    ("realme gt", "Realme GT 5G", "Realme"),
    ("realme gt", "Realme GT 2 Pro 5G", "Realme"),
    ("vivo v27", "vivo V27 5G", "vivo"),
    ("iqoo 11", "iQOO 11 5G", "Iqoo"),
    ("vivo iqoo", "vivo iQOO 7", "vivo"),
    ("iphone 15 pro", "Apple iPhone 15 Pro", "Apple"),
    ("iphone 15", "Apple iPhone 15", "Apple"),
    ("redmi note 13", "Xiaomi Redmi Note 13", "Xiaomi"),
]
for query, target, brand in cases:
    score = calculate_match_score(query, target, brand)
    norm_q = normalize_search_text(query)
    norm_t = normalize_search_text(target)
    print(f"  '{query}' vs '{target}': score={score:.3f}  |  norm_q='{norm_q}'  norm_t='{norm_t}'")

print("\n=== BRAND COMPATIBILITY EDGE CASES ===")
brand_cases = [
    ("iqoo 11", "iQOO 11 5G", "Iqoo"),
    ("vivo iqoo", "vivo iQOO 7", "vivo"),
    ("realme gt", "Realme GT 5G", "Realme"),
]
for q, t, b in brand_cases:
    nq = normalize_search_text(q)
    nt = normalize_search_text(t)
    nb = normalize_search_text(b)
    compat = check_brand_compatibility(nq, nt, nb)
    print(f"  compat('{q}', '{t}', '{b}'): {compat}")

print("\n=== KNOWN BRANDS coverage check ===")
from deprecio.core.fuzzy_search import KNOWN_BRANDS
missing = ['realme', 'vivo', 'iqoo', 'oppo', 'honor', 'oneplus', 'poco']
for b in missing:
    print(f"  '{b}' in KNOWN_BRANDS: {b in KNOWN_BRANDS}")
