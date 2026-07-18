"""End-to-end smoke test for Loyalyn V4 program profiles and stamp experience."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

DB = "/tmp/loyalyn-v4-stamp-qa.db"
Path(DB).unlink(missing_ok=True)
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB}",
    "BOOTSTRAP_ADMIN_EMAIL": "owner-v4@example.com",
    "BOOTSTRAP_ADMIN_PASSWORD": "OwnerPass123!",
    "JWT_SECRET": "x" * 64,
    "ENCRYPTION_KEY": "y" * 64,
    "WALLET_STORAGE_DIR": "/tmp/loyalyn-v4-wallet-qa",
    "PUBLIC_API_URL": "https://api.example.com",
    "PUBLIC_WEB_URL": "https://app.example.com",
})

import httpx
from app.db.session import engine
from app.main import app
from app.models import Base


async def request(client, method, path, *, token=None, expected=200, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.request(method, path, headers=headers, **kwargs)
    if response.status_code != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {response.status_code}: {response.text}")
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return response.content


async def login(client, email, password):
    data = await request(client, "POST", "/api/auth/login", json={"email": email, "password": password})
    return data["access_token"]


async def main():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            owner = await login(client, "owner-v4@example.com", "OwnerPass123!")
            created = await request(client, "POST", "/api/brands", token=owner, expected=201, json={
                "name": "ONA Coffee", "slug": "ona-coffee", "primary_color": "#70050B",
                "accent_color": "#C6FF4A", "currency": "QAR", "timezone": "Asia/Qatar", "locale": "ar",
                "program_mode": "stamps_only", "manager_name": "ONA Manager",
                "manager_email": "manager-v4@example.com", "manager_password": "ManagerPass123!",
            })
            brand = created["brand"]
            brand_id = brand["id"]
            assert brand["program_mode"] == "stamps_only"
            assert brand["capabilities"]["stamps"] is True
            assert brand["capabilities"]["points"] is False
            assert brand["capabilities"]["multi_stamp_cards"] is True

            manager = await login(client, "manager-v4@example.com", "ManagerPass123!")
            programs = await request(client, "GET", f"/api/stamps/programs?brand_id={brand_id}", token=manager)
            assert len(programs) == 1
            coffee = programs[0]
            coffee = await request(client, "PATCH", f"/api/stamps/programs/{coffee['id']}", token=manager, json={
                "name": "قهوة", "slug": "coffee", "required_stamps": 2,
                "reward_title": "قهوة مجانية", "stamp_icon": "coffee",
                "background_color": "#70050B", "accent_color": "#C6FF4A",
            })
            sweet = await request(client, "POST", "/api/stamps/programs", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "سويت", "slug": "sweet", "description": "حلويات",
                "required_stamps": 4, "reward_title": "سويت مجاني", "reward_type": "free_item",
                "stamp_icon": "cake", "background_color": "#40192A", "accent_color": "#FFB6C1",
                "is_default": False, "sort_order": 2, "is_active": True,
            })

            public_profile = await request(client, "GET", "/api/public/brands/ona-coffee")
            assert len(public_profile["programs"]) == 2
            qr = await request(client, "GET", "/api/public/brands/ona-coffee/join-qr.svg")
            assert qr.startswith(b"<?xml") or b"<svg" in qr[:300]
            joined = await request(client, "POST", "/api/public/brands/ona-coffee/join", expected=201, json={
                "name": "Ahmed", "phone": "55512345", "email": None, "birthday": None,
                "selected_program_ids": [coffee["id"], sweet["id"]],
            })
            customer_id = joined["customer"]["id"]
            code = joined["customer"]["membership_code"]
            assert {x["slug"] for x in joined["cards"]} == {"coffee", "sweet"}

            scan = await request(client, "GET", f"/api/stamps/scan/{code}?brand_id={brand_id}", token=manager)
            assert len(scan["cards"]) == 2
            first = await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{coffee['id']}/add", token=manager, json={
                "quantity": 1, "branch_id": None, "idempotency_key": "coffee-stamp-1",
            })
            assert next(x for x in first["cards"] if x["slug"] == "coffee")["stamps"] == 1
            duplicate = await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{coffee['id']}/add", token=manager, json={
                "quantity": 1, "branch_id": None, "idempotency_key": "coffee-stamp-1",
            })
            assert duplicate["duplicate"] is True
            second = await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{coffee['id']}/add", token=manager, json={
                "quantity": 1, "branch_id": None, "idempotency_key": "coffee-stamp-2",
            })
            coffee_card = next(x for x in second["cards"] if x["slug"] == "coffee")
            sweet_card = next(x for x in second["cards"] if x["slug"] == "sweet")
            assert coffee_card["stamps"] == 0 and coffee_card["rewards_available"] == 1
            assert sweet_card["stamps"] == 0 and sweet_card["rewards_available"] == 0

            sweet_added = await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{sweet['id']}/add", token=manager, json={
                "quantity": 1, "branch_id": None, "idempotency_key": "sweet-stamp-1",
            })
            assert next(x for x in sweet_added["cards"] if x["slug"] == "sweet")["stamps"] == 1
            assert next(x for x in sweet_added["cards"] if x["slug"] == "coffee")["rewards_available"] == 1

            redeemed = await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{coffee['id']}/redeem", token=manager, json={
                "branch_id": None, "idempotency_key": "coffee-redeem-1",
            })
            assert redeemed["reward_title"] == "قهوة مجانية"
            assert next(x for x in redeemed["cards"] if x["slug"] == "coffee")["rewards_available"] == 0

            # A stamps-only brand cannot accidentally use the legacy generic visit or point reward flow.
            await request(client, "POST", f"/api/customers/{customer_id}/loyalty", token=manager, expected=409, json={
                "action": "visit", "amount": 0, "points": 0, "stamps": 0,
                "idempotency_key": "legacy-visit-blocked",
            })
            await request(client, "POST", "/api/management/rewards", token=manager, expected=409, json={
                "brand_id": brand_id, "name": "Point Reward", "points_cost": 100,
            })

            # Change the account to full mode and verify stamp history is preserved.
            full = await request(client, "PATCH", f"/api/brands/{brand_id}/program-profile", token=manager, json={
                "program_mode": "full", "feature_flags": {}, "join_enabled": True,
                "join_require_email": False, "join_welcome_text": "Welcome",
            })
            assert full["capabilities"]["points"] is True and full["capabilities"]["stamps"] is True
            after_switch = await request(client, "GET", f"/api/stamps/scan/{code}?brand_id={brand_id}", token=manager)
            assert next(x for x in after_switch["cards"] if x["slug"] == "sweet")["stamps"] == 1

            # Custom profile disables campaigns at server level without deleting anything.
            custom = await request(client, "PATCH", f"/api/brands/{brand_id}/program-profile", token=manager, json={
                "program_mode": "custom", "feature_flags": {"campaigns": False, "stamps": True, "multi_stamp_cards": True, "fast_scan": True, "points": False, "cashback": False, "tiers": False, "rewards": True, "coupons": False, "wallet": True},
                "join_enabled": True, "join_require_email": False,
            })
            assert custom["capabilities"]["campaigns"] is False
            await request(client, "GET", f"/api/notifications/campaigns?brand_id={brand_id}", token=manager, expected=409)

            dashboard = await request(client, "GET", f"/api/dashboard?brand_id={brand_id}", token=manager)
            assert dashboard["stamps_issued"] == 3
            assert dashboard["stamp_rewards_redeemed"] == 1

            print(json.dumps({
                "ok": True, "version": "4.1.0", "brand": brand_id,
                "programs": ["coffee", "sweet"], "independent_balances": True,
                "public_join": True, "stable_qr": True, "fast_scan": True,
                "legacy_features_preserved_after_mode_switch": True,
                "server_side_feature_gates": True,
            }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
