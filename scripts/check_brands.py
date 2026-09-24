import sqlite3
conn = sqlite3.connect('data/global_devices.db')
cur = conn.cursor()

cur.execute("SELECT DISTINCT brand FROM phones WHERE LOWER(brand) LIKE '%iqoo%'")
print('iQOO brand variants:', cur.fetchall())

cur.execute("SELECT DISTINCT brand FROM phones WHERE LOWER(brand) LIKE '%vivo%'")
print('Vivo brand variants:', cur.fetchall())

cur.execute("SELECT brand, COUNT(*) FROM phones WHERE LOWER(brand) LIKE '%iqoo%' OR LOWER(brand) LIKE '%vivo%' GROUP BY brand")
print('Counts:', cur.fetchall())

cur.execute("SELECT brand, name FROM phones WHERE LOWER(clean_name) LIKE '%poco x6%'")
print('POCO X6 all:', cur.fetchall())

cur.execute("SELECT brand, name FROM phones WHERE LOWER(clean_name) LIKE '%redmi note 13%'")
print('Redmi Note 13 all:', cur.fetchall())

# Check iQOO in clean_name
cur.execute("SELECT brand, name, clean_name FROM phones WHERE LOWER(clean_name) LIKE '%iqoo%' LIMIT 10")
print('iQOO in clean_name:', cur.fetchall())

# Check brand=Iqoo in search
cur.execute("SELECT brand, name, clean_name FROM phones WHERE LOWER(brand) = 'iqoo' LIMIT 5")
print('brand=iqoo exactly:', cur.fetchall())

conn.close()
