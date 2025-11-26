from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_session_local
from schemas.payments_schemas import InitiateSubscriptionRequest, InitiateSubscriptionResponse, VerifyRequest, SubscriptionStatus
from services.flutterwave_client import FlutterwaveClient
from models.payments_models import Subscription
from datetime import datetime, timedelta
import os
import uuid
import httpx

router = APIRouter(prefix="/payments/flutterwave", tags=["payments"])
sub_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])  # alias for mobile app

def get_db():
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from Endpoints.auth import user_dependency  # uses OAuth2 bearer to set user context


async def _convert_usd(amount_usd: float, to_currency: str) -> float:
    to_currency = (to_currency or "USD").upper()
    if to_currency == "USD":
        return float(amount_usd)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.exchangerate.host/convert", params={"from": "USD", "to": to_currency, "amount": amount_usd})
            r.raise_for_status()
            data = r.json()
            result = data.get("result")
            if result is None:
                raise ValueError("no conversion result")
            return float(result)
    except Exception:
        # Fallback multipliers (approximate; only used if API unavailable)
        fallback = {"NGN": 1500.0, "UGX": 3800.0, "RWF": 1300.0}
        rate = fallback.get(to_currency)
        if rate:
            return float(amount_usd) * rate
        return float(amount_usd)


def _round_for_currency(amount: float, currency: str) -> float:
    zero_decimal = {"UGX", "RWF"}
    return round(amount, 0 if currency.upper() in zero_decimal else 2)


@router.post("/initiate", response_model=InitiateSubscriptionResponse)
async def initiate_subscription(payload: InitiateSubscriptionRequest, user: user_dependency, request: Request, db: Session = Depends(get_db)):
    """Initiate a subscription payment. Attaches user_id in meta so webhook can map the event."""
    user_id = int(user.get("user_id"))
    user_email = request.headers.get("X-User-Email", f"user{user_id}@brainink.org")

    try:
        client = FlutterwaveClient()
    except RuntimeError as e:
        # FlutterwaveClient raises RuntimeError when FLW_SECRET_KEY is not configured
        raise HTTPException(status_code=503, detail="Payment service is not configured. Please contact support.")
    
    try:
        # Convert $5 equivalent when charging non-USD currencies
        target_currency = (payload.currency or "USD").upper()
        amount_to_charge = payload.amount
        if target_currency != "USD":
            converted = await _convert_usd(payload.amount, target_currency)
            amount_to_charge = _round_for_currency(converted, target_currency)

        plan_id = await client.ensure_plan(amount=amount_to_charge, currency=target_currency, interval=payload.interval)
        tx_ref = f"sub_{user_id}_{uuid.uuid4().hex[:10]}"
        res = await client.create_payment(
            email=user_email,
            amount=amount_to_charge,
            currency=target_currency,
            plan_id=plan_id,
            tx_ref=tx_ref,
            meta={"user_id": user_id, "country": {"USD":"US","NGN":"NG","UGX":"UG","RWF":"RW"}.get(target_currency, "US")}
        )
        checkout_url = res.get("data", {}).get("link")
        if not checkout_url:
            raise HTTPException(status_code=502, detail="Flutterwave did not return a checkout link")
        return InitiateSubscriptionResponse(checkoutUrl=checkout_url, paymentReference=tx_ref)
    finally:
        await client.close()


@router.post("/verify", response_model=SubscriptionStatus)
async def verify_subscription(req: VerifyRequest, user: user_dependency, db: Session = Depends(get_db)):
    user_id = int(user.get("user_id"))
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
    """Flutterwave webhook handler.
    Expects verif-hash header to match FLW_WEBHOOK_SECRET.
    Uses meta.user_id (attached during initiation) to update subscription.
    Handles: charge.completed, subscription.charge.completed
    """
    secret_hash = os.getenv("FLW_WEBHOOK_SECRET", "")
    payload = await request.json()
    signature = request.headers.get("verif-hash")
    if secret_hash and signature != secret_hash:
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = payload.get("event") or payload.get("event.type")
    data = payload.get("data", {})
    meta = data.get("meta", {}) or {}
    user_id = meta.get("user_id")

    if user_id is None:
        # Fallback attempt: map by email if meta missing
        email = data.get("customer", {}).get("email")
        # TODO: look up user by email in users table. For now ignore if no user_id.
        return {"skipped": True, "reason": "missing user_id meta"}

    # Only proceed on relevant events
    if event_type in {"charge.completed", "subscription.charge.completed"}:
        try:
            user_id_int = int(user_id)
        except ValueError:
            return {"skipped": True, "reason": "invalid user_id meta"}
        sub = db.query(Subscription).filter(Subscription.user_id == user_id_int).one_or_none()
        now = datetime.utcnow()
        # Determine next period end: if subscription cycle info provided use it else +30 days
        cycle_end = now + timedelta(days=30)
        plan_info = data.get("plan", {})
        interval = plan_info.get("interval")  # e.g., monthly
        if interval == "monthly":
            cycle_end = now + timedelta(days=30)
        if not sub:
            sub = Subscription(user_id=user_id_int, active=True, status="active", current_period_end=cycle_end, last_payment_id=data.get("id"))
            db.add(sub)
        else:
            sub.active = True
            sub.status = "active"
            sub.current_period_end = cycle_end
            sub.last_payment_id = data.get("id")
        db.commit()
        db.refresh(sub)
        return {"updated": True, "user_id": user_id_int, "expires": sub.current_period_end.isoformat()}

    return {"ignored": True, "event": event_type}


@router.get("/status", response_model=SubscriptionStatus)
async def get_status(user: user_dependency, db: Session = Depends(get_db)):
    user_id = int(user.get("user_id"))
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).one_or_none()
    if not sub or not sub.active:
        return SubscriptionStatus(active=False)
    return SubscriptionStatus(active=True, expiresAt=sub.current_period_end, lastPaymentId=sub.last_payment_id)


@sub_router.get("/status", response_model=SubscriptionStatus)
async def get_status_alias(user: user_dependency, db: Session = Depends(get_db)):
    # alias path used by mobile client
    return await get_status(user=user, db=db)


@router.get("/_debug/config")
async def payments_debug_config(db: Session = Depends(get_db)):
    """Return non-sensitive payment configuration and DB status for diagnostics.
    Secrets are redacted. Intended for admin troubleshooting only.
    """
    from services.flutterwave_client import FLW_BASE, FLW_PUBLIC_KEY, FLW_SECRET_KEY, FLW_PLAN_ID, FLW_REDIRECT_URL
    # DB ping
    db_ok = True
    try:
        # Lightweight query to check DB
        _ = db.execute("SELECT 1").scalar()
    except Exception:
        db_ok = False

    return {
        "db": {"connected": db_ok},
        "flutterwave": {
            "base": FLW_BASE,
            "public_key_present": bool(FLW_PUBLIC_KEY),
            "secret_key_present": bool(FLW_SECRET_KEY),
            "plan_id": FLW_PLAN_ID or None,
            "redirect_url": FLW_REDIRECT_URL or None,
        },
        "routes": {
            "initiate": "/payments/flutterwave/initiate",
            "verify": "/payments/flutterwave/verify",
            "status": "/payments/flutterwave/status",
            "webhook": "/payments/flutterwave/webhook",
            "alias_status": "/subscriptions/status",
        }
    }
