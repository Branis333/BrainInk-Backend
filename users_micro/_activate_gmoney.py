"""Activate gmoney's subscription with the correct schema."""
import os, sys
from dotenv import load_dotenv
load_dotenv()

from db.database import get_engine
from sqlalchemy import text
from datetime import datetime, timedelta

engine = get_engine()
with engine.connect() as conn:
    # Check if gmoney already has a subscription row
    r = conn.execute(text("SELECT id FROM subscriptions WHERE user_id = 55"))
    row = r.fetchone()
    
    expires = datetime.utcnow() + timedelta(days=365)
    now = datetime.utcnow()
    
    if row:
        conn.execute(text(
            "UPDATE subscriptions SET active=true, status='active', provider='admin', "
            "current_period_end=:exp, last_payment_id='admin_manual', updated_at=:now "
            "WHERE user_id=55"
        ), {"exp": expires, "now": now})
        print(f"Updated existing subscription for gmoney (user_id=55)")
    else:
        conn.execute(text(
            "INSERT INTO subscriptions (user_id, provider, status, active, current_period_end, last_payment_id, created_at, updated_at) "
            "VALUES (55, 'admin', 'active', true, :exp, 'admin_manual', :now, :now)"
        ), {"exp": expires, "now": now})
        print(f"Created new subscription for gmoney (user_id=55)")
    
    conn.commit()
    
    # Verify
    r = conn.execute(text("SELECT * FROM subscriptions WHERE user_id = 55"))
    row = r.fetchone()
    print(f"Subscription row: {row}")
    print(f"Expires: {expires.isoformat()}")
    print("SUCCESS: gmoney is now a paid user!")
