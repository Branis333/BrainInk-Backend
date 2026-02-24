import os
import httpx
from typing import Any, Dict


FLW_BASE = os.getenv("FLW_BASE", "https://api.flutterwave.com")
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "")
FLW_PUBLIC_KEY = os.getenv("FLW_PUBLIC_KEY", "")
FLW_PLAN_ID = os.getenv("FLW_PLAN_ID", "")  # optional; set after creating plan
FLW_REDIRECT_URL = os.getenv("FLW_REDIRECT_URL", "")  # optional


class FlutterwaveClient:
    def __init__(self):
        if not FLW_SECRET_KEY:
            raise RuntimeError("Payment service not configured. FLW_SECRET_KEY environment variable is required.")
        self.client = httpx.AsyncClient(base_url=FLW_BASE, headers={
            "Authorization": f"Bearer {FLW_SECRET_KEY}",
            "Content-Type": "application/json"
        }, timeout=30)

    async def ensure_plan(self, amount: float, currency: str, interval: str, name: str = "Afterskool Monthly") -> str:
        """Ensure a payment plan exists matching amount/currency/interval.
        If `FLW_PLAN_ID` is set, verify it; if it mismatches, create a fresh plan.
        """
        global FLW_PLAN_ID
        if FLW_PLAN_ID:
            try:
                r = await self.client.get(f"/v3/payment-plans/{FLW_PLAN_ID}")
                r.raise_for_status()
                data = r.json().get("data", {})
                plan_currency = str(data.get("currency", "")).upper()
                plan_amount = float(data.get("amount", 0))
                plan_interval = str(data.get("interval", "")).lower()
                if plan_currency == currency.upper() and abs(plan_amount - float(amount)) < 0.0001 and plan_interval == interval.lower():
                    return FLW_PLAN_ID
            except Exception:
                # If verification fails, fall back to creating a new plan
                pass
        # Create plan
        payload = {
            "amount": amount,
            "name": name,
            "interval": interval,
            "currency": currency
        }
        r = await self.client.post("/v3/payment-plans", json=payload)
        r.raise_for_status()
        data = r.json()
        plan_id = str(data.get("data", {}).get("id"))
        FLW_PLAN_ID = plan_id
        return plan_id

    async def create_payment(self, email: str, amount: float, currency: str, plan_id: str, tx_ref: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        currency = currency.upper()
        # Prefer MoMo options where applicable
        mo_options = {
            "UGX": "mobilemoneyuganda",
            "RWF": "mobilemoneyrwanda",
            "GHS": "mobilemoneygh",
            "ZMW": "mobilemoneyzambia",
        }
        payment_options = ["card", "banktransfer", "ussd"]
        if currency in mo_options:
            payment_options.append(mo_options[currency])
        payload = {
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": currency,
            "redirect_url": FLW_REDIRECT_URL or "https://brainink-backend.onrender.com/payments/flutterwave/callback",
            "payment_plan": plan_id,
            "customer": {"email": email},
            "customizations": {"title": "Afterskool Subscription", "description": "Monthly access"},
            "meta": meta or {},
            "payment_options": ",".join(payment_options)
        }
        r = await self.client.post("/v3/payments", json=payload)
        r.raise_for_status()
        return r.json()

    async def verify_transaction(self, transaction_id: str) -> Dict[str, Any]:
        r = await self.client.get(f"/v3/transactions/{transaction_id}/verify")
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self.client.aclose()
