import sqlite3

conn = sqlite3.connect('data/global_devices.db')
cur = conn.cursor()

# Diagnose duplicates from case issues
print('=== BRANDS WITH CASE DUPLICATES ===')
cur.execute('SELECT LOWER(brand), COUNT(DISTINCT brand), GROUP_CONCAT(DISTINCT brand) FROM phones GROUP BY LOWER(brand) HAVING COUNT(DISTINCT brand) > 1')
for row in cur.fetchall():
    print(row)

# Check what models Realme has in current DB - any year range?
print('\n=== REALME YEAR COVERAGE ===')
cur.execute('''
    SELECT 
        CASE 
            WHEN json_extract(raw_specs, "$.release_date") IS NOT NULL THEN SUBSTR(json_extract(raw_specs, "$.release_date"), 1, 4)
            ELSE "unknown"
        END as year,
        COUNT(*) 
    FROM phones WHERE LOWER(brand) = "realme"
    GROUP BY year ORDER BY year
''')
for row in cur.fetchall():
    print(row)

print('\n=== REALME LATEST MODELS ===')
cur.execute('SELECT brand, name FROM phones WHERE LOWER(brand) = "realme" ORDER BY name DESC LIMIT 20')
for row in cur.fetchall():
    print(row)

print('\n=== VIVO LATEST MODELS ===')
cur.execute('SELECT brand, name FROM phones WHERE LOWER(brand) IN ("vivo", "Vivo") ORDER BY name DESC LIMIT 20')
for row in cur.fetchall():
    print(row)

print('\n=== IQOO MODELS ===')
cur.execute('SELECT brand, name FROM phones WHERE LOWER(brand) IN ("iqoo", "Iqoo") LIMIT 20')
for row in cur.fetchall():
    print(row)

# Check search logic - what does normalize_search_text produce for these brands?
print('\n=== SAMPLE CLEAN NAMES FOR REALME ===')
cur.execute('SELECT name, clean_name FROM phones WHERE LOWER(brand) = "realme" LIMIT 10')
for row in cur.fetchall():
    print(row)

# What happens when searching "realme gt"
print('\n=== SEARCH SIM: realme gt ===')
tokens = ['realme', 'gt']
clauses = " AND ".join([f"clean_name LIKE ?" for _ in tokens])
params = [f"%{t}%" for t in tokens]
cur.execute(f'SELECT brand, name, clean_name FROM phones WHERE {clauses} LIMIT 10', params)
for row in cur.fetchall():
    print(row)

conn.close()
