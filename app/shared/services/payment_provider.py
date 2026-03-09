"""
Abstract PaymentProvider interface.

All payment providers (Razorpay, Stripe, etc.) implement this interface.
billing_service.py takes a PaymentProvider instance and orchestrates everything.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class PaymentProvider(ABC):
    """Abstract base class for payment provider integrations."""

    @abstractmethod
    async def create_customer(
        self, name: str, email: str, **kwargs
    ) -> dict[str, Any]:
        """Create a customer on the provider. Returns provider-specific data including provider_id."""
        ...

    @abstractmethod
    async def create_subscription(
        self,
        provider_customer_id: str,
        provider_plan_id: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a subscription on the provider. Returns provider-specific data."""
        ...

    @abstractmethod
    async def cancel_subscription(
        self, provider_subscription_id: str, at_period_end: bool = True
    ) -> dict[str, Any]:
        """Cancel a subscription on the provider."""
        ...

    @abstractmethod
    async def create_order(
        self,
        amount: int,
        currency: str,
        receipt: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a payment order/intent. Returns provider-specific data."""
        ...

    @abstractmethod
    async def verify_payment(
        self, provider_payment_id: str, provider_signature: str, **kwargs
    ) -> bool:
        """Verify a payment signature/status with the provider."""
        ...

    @abstractmethod
    async def process_refund(
        self,
        provider_payment_id: str,
        amount: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Process a refund. amount=None means full refund."""
        ...

    @abstractmethod
    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """Verify that a webhook payload was signed by the provider."""
        ...
