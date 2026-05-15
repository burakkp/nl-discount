import psycopg2

url = "postgresql://postgres.hxmrpayksumuzulskkvz:pyFMtrRo9vKf3f@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"

try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("ALTER TABLE discounts ADD COLUMN IF NOT EXISTS original_price FLOAT;")
    cur.execute("ALTER TABLE discounts ADD COLUMN IF NOT EXISTS unit_label VARCHAR;")
    conn.commit()
    print("Migration successful")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
