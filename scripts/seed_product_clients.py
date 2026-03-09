"""
Seed script: generate and insert ProductClient records for each product.

Usage:
    python scripts/seed_product_clients.py

Generates one client key per product in settings.products.
Keys are in the format: pk_{product}_{random_16_chars}

Prints generated keys so they can be copied into each frontend app's .env:
    NEXT_PUBLIC_PRODUCT_CLIENT_KEY=pk_alpha_a8f3k2...

Run this once per environment. Re-running with --force will rotate existing keys.
"""
import asyncio
import secrets
import string
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.shared.models.product_client import ProductClient  # noqa: F401 — register model
from sqlalchemy import select


_ALPHABET = string.ascii_lowercase + string.digits


def _generate_key(product: str) -> str:
    random_part = "".join(secrets.choice(_ALPHABET) for _ in range(16))
    return f"pk_{product}_{random_part}"


async def seed(force: bool = False) -> None:
    dev_origins = ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"]

    async with AsyncSessionFactory() as session:
        for product in settings.products:
            # Check if a key already exists for this product
            existing = await session.execute(
                select(ProductClient).where(
                    ProductClient.product == product,
                    ProductClient.is_active.is_(True),
                )
            )
            record = existing.scalar_one_or_none()

            if record and not force:
                print(f"[{product}] Key already exists — skipping (use --force to rotate)")
                print(f"         X-Product-Client-Key: {record.client_key}")
                continue

            if record and force:
                record.is_active = False
                await session.flush()
                print(f"[{product}] Rotated old key: {record.client_key}")

            new_key = _generate_key(product)
            client = ProductClient(
                product=product,
                client_key=new_key,
                allowed_origins=dev_origins,
                is_active=True,
            )
            session.add(client)
            await session.flush()

            print(f"\n[{product}] Generated new client key:")
            print(f"  X-Product-Client-Key : {new_key}")
            print(f"  Allowed origins      : {dev_origins}")
            print(f"  Add to your frontend .env:")
            print(f"    NEXT_PUBLIC_PRODUCT_CLIENT_KEY={new_key}")

        await session.commit()

    print("\nDone. Add X-Product-Client-Key to every request from the frontend.")
    print("In Postman, add it as a collection variable and include it as a header.\n")


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(seed(force=force))
