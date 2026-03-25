import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("🚨 DATABASE_URL is missing from your .env file!")

engine = create_engine(DATABASE_URL)

sql_commands = [
    # 1. Enable Row Level Security (RLS) on both tables
    "ALTER TABLE public.stores ENABLE ROW LEVEL SECURITY;",
    "ALTER TABLE public.discounts ENABLE ROW LEVEL SECURITY;",
    
    # 2. Create policies to allow public read access (SELECT)
    # This allows anonymous/authenticated users from the Supabase API to read the data.
    "CREATE POLICY \"Allow public read on stores\" ON public.stores FOR SELECT USING (true);",
    "CREATE POLICY \"Allow public read on discounts\" ON public.discounts FOR SELECT USING (true);"
]

print("🛡️ Setting up Row Level Security (RLS) in Supabase...")

try:
    # engine.begin() manages the transaction automatically
    with engine.begin() as conn:
        for cmd in sql_commands:
            # We wrap the command in text() for SQLAlchemy 2.0+ compatibility
            conn.execute(text(cmd))
            print(f"✅ Executed: {cmd.split('ON')[0].strip()} ...")
            
    print("🎉 Successfully enabled RLS and created read policies for Supabase!")
    print("ℹ️ Note: Write operations via the Python script (SQLAlchemy) bypass RLS because it connects as the 'postgres' superuser role.")
except Exception as e:
    print(f"❌ Failed to setup RLS: {e}")
