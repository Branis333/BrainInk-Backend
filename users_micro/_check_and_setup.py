"""One-time script to check/create the gmoney test user and activate their subscription."""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from db.database import get_engine, get_session_local
from sqlalchemy import text
import models.users_models as user_models
import models.payments_models as payments_models

engine = get_engine()

# 1. Ensure subscriptions table exists
print("--- Ensuring subscriptions table ---")
payments_models.Base.metadata.create_all(bind=engine, checkfirst=True)
print("OK: subscriptions table ensured")

SessionLocal = get_session_local()
db = SessionLocal()

try:
    # 2. Check if 'gmoney' user exists
    print("\n--- Checking for 'gmoney' user ---")
    user_row = db.execute(text("SELECT id, username, email FROM users WHERE username='gmoney' OR email='gmoney' LIMIT 1")).fetchone()
    
    if user_row:
        user_id = user_row[0]
        print(f"FOUND: id={user_row[0]}, username={user_row[1]}, email={user_row[2]}")
    else:
        print("NOT FOUND — registering 'gmoney'...")
        import bcrypt
        hashed = bcrypt.hashpw("gmoney".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.execute(text(
            "INSERT INTO users (username, email, password_hash, fname, lname, is_active, email_confirmed, is_verified) "
            "VALUES (:u, :e, :p, :fn, :ln, true, true, true)"
        ), {"u": "gmoney", "e": "gmoney", "p": hashed, "fn": "Test", "ln": "User"})
        db.commit()
        user_row = db.execute(text("SELECT id, username, email FROM users WHERE username='gmoney' LIMIT 1")).fetchone()
        user_id = user_row[0]
        print(f"REGISTERED: id={user_id}, username=gmoney, email=gmoney")

    # 3. Activate subscription for 1 year
    print(f"\n--- Activating subscription for user_id={user_id} ---")
    from datetime import datetime, timedelta
    sub_row = db.execute(text("SELECT id FROM subscriptions WHERE user_id = :uid"), {"uid": user_id}).fetchone()
    expires = datetime.utcnow() + timedelta(days=365)
    
    if sub_row:
        db.execute(text(
            "UPDATE subscriptions SET active=true, status='active', current_period_end=:exp, "
            "last_payment_id='admin_manual', updated_at=NOW() WHERE user_id=:uid"
        ), {"exp": expires, "uid": user_id})
    else:
        db.execute(text(
            "INSERT INTO subscriptions (user_id, active, status, current_period_end, last_payment_id, created_at, updated_at) "
            "VALUES (:uid, true, 'active', :exp, 'admin_manual', NOW(), NOW())"
        ), {"uid": user_id, "exp": expires})
    
    db.commit()
    print(f"OK: Subscription active until {expires.isoformat()}")
    
    print("\n✅ Setup complete! User 'gmoney' / password 'gmoney' is now a paid premium user.")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
