from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_session_local
from schemas.payments_schemas import InitiateSubscriptionRequest, InitiateSubscriptionResponse, VerifyRequest, SubscriptionStatus
from services.flutterwave_client import FlutterwaveClient
from models.payments_models import Subscription
from datetime import datetime, timedelta
import os
import uuid

router = APIRouter(prefix="/payments/flutterwave", tags=["payments"])

def get_db():
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id(request: Request) -> int:
    # Replace with your real auth; for now, extract from request.state if set by auth dependency
    uid = getattr(request.state, "user_id", None)
    if not uid:
        # Try a simple header override for dev/testing
        uid = request.headers.get("X-Debug-UserId")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return int(uid)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id context")


@router.post("/initiate", response_model=InitiateSubscriptionResponse)
async def initiate_subscription(payload: InitiateSubscriptionRequest, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    user_email = request.headers.get("X-User-Email", f"user{user_id}@brainink.org")

    client = FlutterwaveClient()
    try:
        plan_id = await client.ensure_plan(amount=payload.amount, currency=payload.currency, interval=payload.interval)
        tx_ref = f"sub_{user_id}_{uuid.uuid4().hex[:10]}"
        res = await client.create_payment(email=user_email, amount=payload.amount, currency=payload.currency, plan_id=plan_id, tx_ref=tx_ref)
        checkout_url = res.get("data", {}).get("link")
        if not checkout_url:
            raise HTTPException(status_code=502, detail="Flutterwave did not return a checkout link")
        return InitiateSubscriptionResponse(checkoutUrl=checkout_url, paymentReference=tx_ref)
    finally:
        await client.close()


@router.post("/verify", response_model=SubscriptionStatus)
async def verify_subscription(req: VerifyRequest, request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    # Flutterwave sends transaction_id to your redirect URL, but since we only have tx_ref here,
    # you may store mapping in DB or rely on webhook to finalize. For demo, we mark as active for 30 days.
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).one_or_none()
    if not sub:
        sub = Subscription(user_id=user_id, active=True, status="active", current_period_end=datetime.utcnow()+timedelta(days=30))
        db.add(sub)
    else:
        sub.active = True
        sub.status = "active"
        sub.current_period_end = datetime.utcnow()+timedelta(days=30)
    db.commit()
    db.refresh(sub)
    return SubscriptionStatus(active=True, expiresAt=sub.current_period_end, lastPaymentId=sub.last_payment_id)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    # Validate signature header
    secret_hash = os.getenv("FLW_WEBHOOK_SECRET", "")
    payload = await request.json()
    signature = request.headers.get("verif-hash")
    if secret_hash and signature != secret_hash:
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = payload.get("event") or payload.get("event.type")
    data = payload.get("data", {})

    # Identify user by email or meta if you passed it during payment
    email = data.get("customer", {}).get("email")
    # TODO: map email -> user_id via users table; for now accept a header override only in dev
    # If you include user_id in meta when creating the payment, extract it here instead.

    # Update subscription state on charge.completed or subscription.charge.completed
    if "charge.completed" in (event_type or "") or "subscription.charge.completed" in (event_type or ""):
        # You should look up user by email; here we skip and no-op
        pass
    return {"received": True}


@router.get("/status", response_model=SubscriptionStatus)
async def get_status(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).one_or_none()
    if not sub or not sub.active:
        return SubscriptionStatus(active=False)
    return SubscriptionStatus(active=True, expiresAt=sub.current_period_end, lastPaymentId=sub.last_payment_id)
