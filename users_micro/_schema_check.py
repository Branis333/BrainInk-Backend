from dotenv import load_dotenv
load_dotenv()
from db.database import get_engine
from sqlalchemy import text

e = get_engine()
with e.connect() as c:
    r = c.execute(text("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='subscriptions' ORDER BY ordinal_position"))
    print("=== SUBSCRIPTIONS TABLE SCHEMA ===")
    for row in r.fetchall():
        print(row)
    
    print("\n=== SAMPLE DATA ===")
    r2 = c.execute(text("SELECT * FROM subscriptions LIMIT 3"))
    cols = r2.keys()
    print("Columns:", list(cols))
    for row in r2.fetchall():
        print(row)
