"""
Razorpay implementation of PaymentProvider.
This is the PRIMARY payment provider.

Uses the razorpay Python SDK. All calls are wrapped in asyncio.to_thread
since the SDK is synchronous.
"""
import asyncio
import hashlib
import hmac
import logging
from typing import Any

from app.core.config import settings
from app.shared.services.payment_provider import PaymentProvider

logger = logging.getLogger(__name__)


class RazorpayProvider(PaymentProvider):
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import razorpay

                self._client = razorpay.Client(
                    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
                )
            except ImportError:
                raise RuntimeError(
                    "razorpay package not installed. Run: pip install razorpay"
                )
        return self._client

    async def create_customer(
        self, name: str, email: str, **kwargs
    ) -> dict[str, Any]:
        data = {"name": name, "email": email, **kwargs}
        result = await asyncio.to_thread(self.client.customer.create, data)
        return {
            "provider_id": result["id"],
            "raw": result,
        }

    async def create_subscription(
        self,
        provider_customer_id: str,
        provider_plan_id: str,
        **kwargs,
    ) -> dict[str, Any]:
        data = {
            "plan_id": provider_plan_id,
            "customer_id": provider_customer_id,
            "total_count": kwargs.get("total_count", 12),
            **{k: v for k, v in kwargs.items() if k != "total_count"},
        }
        result = await asyncio.to_thread(self.client.subscription.create, data)
        return {
            "provider_id": result["id"],
            "status": result.get("status"),
            "raw": result,
        }

    async def cancel_subscription(
        self, provider_subscription_id: str, at_period_end: bool = True
    ) -> dict[str, Any]:
        result = await asyncio.to_thread(
            self.client.subscription.cancel,
            provider_subscription_id,
            {"cancel_at_cycle_end": 1 if at_period_end else 0},
        )
        return {
            "provider_id": result["id"],
            "status": result.get("status"),
            "raw": result,
        }

    async def create_order(
        self,
        amount: int,
        currency: str,
        receipt: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "amount": amount,
            "currency": currency.upper(),
        }
        if receipt:
            data["receipt"] = receipt
        data.update(kwargs)
        result = await asyncio.to_thread(self.client.order.create, data)
        return {
            "provider_id": result["id"],
            "status": result.get("status"),
            "raw": result,
        }

    async def verify_payment(
        self, provider_payment_id: str, provider_signature: str, **kwargs
    ) -> bool:
        try:
            params = {
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": provider_signature,
            }
            if "razorpay_order_id" in kwargs:
                params["razorpay_order_id"] = kwargs["razorpay_order_id"]
            elif "razorpay_subscription_id" in kwargs:
                params["razorpay_subscription_id"] = kwargs[
                    "razorpay_subscription_id"
                ]
            self.client.utility.verify_payment_signature(params)
            return True
        except Exception:
            return False

    async def process_refund(
        self,
        provider_payment_id: str,
        amount: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if amount is not None:
            data["amount"] = amount
        data.update(kwargs)
        result = await asyncio.to_thread(
            self.client.payment.refund, provider_payment_id, data
        )
        return {
            "provider_id": result["id"],
            "status": result.get("status"),
            "raw": result,
        }

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        expected = hmac.new(
            settings.razorpay_webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
