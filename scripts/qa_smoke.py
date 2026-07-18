"""End-to-end API smoke test for Loyalyn.

Runs against an isolated SQLite database and never touches production data.
Usage from the repository root:
    PYTHONPATH=backend python scripts/qa_smoke.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

DB = "/tmp/loyalyn-v3-qa.db"
Path(DB).unlink(missing_ok=True)
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB}",
    "BOOTSTRAP_ADMIN_EMAIL": "owner@example.com",
    "BOOTSTRAP_ADMIN_PASSWORD": "OwnerPass123!",
    "JWT_SECRET": "x" * 64,
    "ENCRYPTION_KEY": "y" * 64,
    "WALLET_STORAGE_DIR": "/tmp/loyalyn-v3-wallet-qa",
    "PUBLIC_API_URL": "https://api.example.com",
    "PUBLIC_WEB_URL": "https://app.example.com",
})

import httpx
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models import Base
from app.services.campaigns import process_due_campaigns


async def request(client, method, path, *, token=None, expected=200, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.request(method, path, headers=headers, **kwargs)
    if response.status_code != expected:
        raise AssertionError(
            f"{method} {path}: expected {expected}, got {response.status_code}: {response.text}"
        )
    try:
        return response.json()
    except Exception:
        return response.content


async def login(client, email, password):
    return (await request(client, "POST", "/api/auth/login", json={"email": email, "password": password}))["access_token"]


async def deliver_campaign(client, token, brand_id, payload):
    campaign = await request(
        client, "POST", "/api/notifications/campaigns", token=token, expected=201, json=payload
    )
    assert campaign["status"] == "queued"
    async with AsyncSessionLocal() as db:
        await process_due_campaigns(db)
    rows = await request(client, "GET", f"/api/notifications/campaigns?brand_id={brand_id}", token=token)
    return next(row for row in rows if row["id"] == campaign["id"])


async def main():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            owner = await login(client, "owner@example.com", "OwnerPass123!")
            first = await request(client, "POST", "/api/brands", token=owner, expected=201, json={
                "name": "Coffee House", "slug": "coffee-house", "primary_color": "#111827",
                "accent_color": "#C6FF4A", "currency": "QAR", "timezone": "Asia/Qatar", "locale": "ar",
                "manager_name": "Brand Manager", "manager_email": "manager@example.com",
                "manager_password": "ManagerPass123!",
            })
            brand_id = first["brand"]["id"]
            second = await request(client, "POST", "/api/brands", token=owner, expected=201, json={
                "name": "Restaurant", "slug": "restaurant", "primary_color": "#201525",
                "accent_color": "#FFB86C", "currency": "QAR", "timezone": "Asia/Qatar", "locale": "ar",
            })
            second_brand_id = second["brand"]["id"]
            manager = await login(client, "manager@example.com", "ManagerPass123!")
            profile = await request(client, "GET", "/api/auth/me", token=manager)
            assert {x["id"] for x in profile["brands"]} == {brand_id}
            await request(client, "GET", f"/api/customers?brand_id={second_brand_id}", token=manager, expected=403)
            await request(client, "GET", "/api/wallet/platform/credential", token=manager, expected=403)

            # Platform owner can attach an existing account to another brand without replacing its password.
            await request(client, "POST", "/api/management/staff", token=owner, expected=201, json={
                "brand_id": second_brand_id, "name": "Brand Manager", "email": "manager@example.com",
                "role": "brand_admin", "password": "MustNotReplace123!", "permissions": {},
            })
            await login(client, "manager@example.com", "ManagerPass123!")
            await request(client, "POST", "/api/auth/login", expected=401, json={"email": "manager@example.com", "password": "MustNotReplace123!"})
            profile = await request(client, "GET", "/api/auth/me", token=manager)
            assert {x["id"] for x in profile["brands"]} == {brand_id, second_brand_id}

            branch = await request(client, "POST", "/api/management/branches", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "West Bay", "address": "Doha",
            })
            other_branch = await request(client, "POST", "/api/management/branches", token=owner, expected=201, json={
                "brand_id": second_brand_id, "name": "Lusail", "address": "Qatar",
            })
            employee = await request(client, "POST", "/api/management/staff", token=manager, expected=201, json={
                "brand_id": brand_id, "branch_id": branch["id"], "name": "Cashier",
                "email": "cashier@example.com", "role": "employee", "password": "CashierPass123!", "permissions": {},
            })
            cashier = await login(client, "cashier@example.com", "CashierPass123!")
            await request(client, "GET", f"/api/management/staff?brand_id={brand_id}", token=cashier, expected=403)

            await request(client, "POST", "/api/customers", token=manager, expected=400, json={
                "brand_id": brand_id, "home_branch_id": other_branch["id"],
                "name": "Wrong Branch", "phone": "55500000",
            })
            customer = await request(client, "POST", "/api/customers", token=manager, expected=201, json={
                "brand_id": brand_id, "home_branch_id": branch["id"], "name": "Ahmed",
                "phone": "55512345", "email": "ahmed@example.com", "tags": ["vip"],
            })
            customer_id = customer["id"]
            assert customer["home_branch_id"] == branch["id"]
            second_customer = await request(client, "POST", "/api/customers", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "Mona", "phone": "55567890", "email": "mona@example.com",
            })
            await request(client, "PUT", f"/api/customers/program/{brand_id}", token=manager, json={
                "enabled": True, "program_type": "hybrid", "points_per_visit": 10,
                "points_per_currency": 2, "required_stamps": 2, "stamp_reward_title": "Free Coffee",
                "reward_points": 100, "reward_title": "Free", "birthday_bonus": 50,
                "referral_bonus": 20, "cashback_percent": 0, "points_expiry_days": 30,
                "daily_points_cap": 500, "allow_manual_adjustment": True,
                "rules": {"auto_convert_points": False, "global_multiplier": 1},
            })

            # Cross-brand branch is rejected even for an otherwise authorized actor.
            await request(client, "POST", f"/api/customers/{customer_id}/loyalty", token=cashier, expected=400, json={
                "action": "visit", "branch_id": other_branch["id"], "amount": 0, "points": 0,
                "stamps": 0, "idempotency_key": "cross-branch-0001",
            })
            first_visit = await request(client, "POST", f"/api/customers/{customer_id}/loyalty", token=cashier, json={
                "action": "visit", "branch_id": branch["id"], "amount": 0, "points": 0,
                "stamps": 0, "idempotency_key": "visit-00000001",
            })
            assert first_visit["customer"]["points"] == 10 and first_visit["customer"]["stamps"] == 1
            duplicate = await request(client, "POST", f"/api/customers/{customer_id}/loyalty", token=cashier, json={
                "action": "visit", "branch_id": branch["id"], "amount": 0, "points": 0,
                "stamps": 0, "idempotency_key": "visit-00000001",
            })
            assert duplicate["duplicate"] is True and duplicate["customer"]["points"] == 10
            second_visit = await request(client, "POST", f"/api/customers/{customer_id}/loyalty", token=cashier, json={
                "action": "visit", "branch_id": branch["id"], "amount": 0, "points": 0,
                "stamps": 0, "idempotency_key": "visit-00000002",
            })
            assert second_visit["customer"]["available_rewards"] == 1 and second_visit["customer"]["stamps"] == 0

            earned = await request(client, "POST", f"/api/customers/{customer_id}/redeem-earned", token=cashier, json={
                "branch_id": branch["id"], "idempotency_key": "earned-0000001",
            })
            assert earned["customer"]["available_rewards"] == 0
            restored_earned = await request(client, "POST", f"/api/customers/transactions/{earned['transaction']['id']}/reverse", token=manager, json={
                "reason": "اختبار عكس صرف المكافأة", "idempotency_key": "reverse-earned-0001",
            })
            assert restored_earned["customer"]["available_rewards"] == 1

            spend = await request(client, "POST", f"/api/customers/{customer_id}/loyalty", token=cashier, json={
                "action": "spend", "branch_id": branch["id"], "amount": "100", "points": 0,
                "stamps": 0, "idempotency_key": "spend-0000001",
            })
            assert spend["customer"]["points"] == 220

            reward = await request(client, "POST", "/api/management/rewards", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "Cake", "points_cost": 100, "stock": 2,
            })
            reward = await request(client, "PATCH", f"/api/management/rewards/{reward['id']}", token=manager, json={
                "name": "Chocolate Cake", "points_cost": 100, "stock": 2, "is_active": True,
            })
            assert reward["name"] == "Chocolate Cake"
            redeemed = await request(client, "POST", f"/api/customers/{customer_id}/redeem", token=cashier, json={
                "reward_id": reward["id"], "branch_id": branch["id"], "idempotency_key": "redeem-0000001",
            })
            assert redeemed["customer"]["points"] == 120
            ledger = await request(client, "GET", f"/api/customers/{customer_id}/ledger", token=manager)
            reward_tx = next(x for x in ledger if x["action"] == "redeem_reward")
            reward_reversal = await request(client, "POST", f"/api/customers/transactions/{reward_tx['id']}/reverse", token=manager, json={
                "reason": "إلغاء استبدال تجريبي", "idempotency_key": "reverse-reward-0001",
            })
            assert reward_reversal["customer"]["points"] == 220

            coupon = await request(client, "POST", "/api/management/coupons", token=manager, expected=201, json={
                "brand_id": brand_id, "code": "WELCOME25", "name": "ترحيب", "reward_type": "points",
                "reward_value": 25, "max_redemptions": 100, "per_customer_limit": 1,
            })
            coupon = await request(client, "PATCH", f"/api/management/coupons/{coupon['id']}", token=manager, json={
                "name": "ترحيب جديد", "reward_value": 25, "is_active": True,
            })
            applied_coupon = await request(client, "POST", f"/api/customers/{customer_id}/coupons/redeem", token=cashier, json={
                "code": "welcome25", "branch_id": branch["id"], "idempotency_key": "coupon-0000001",
            })
            assert applied_coupon["customer"]["points"] == 245
            same_coupon = await request(client, "POST", f"/api/customers/{customer_id}/coupons/redeem", token=cashier, json={
                "code": "WELCOME25", "branch_id": branch["id"], "idempotency_key": "coupon-0000001",
            })
            assert same_coupon["duplicate"] is True and same_coupon["customer"]["points"] == 245

            tiers = await request(client, "GET", f"/api/management/tiers?brand_id={brand_id}", token=manager)
            tier = await request(client, "PATCH", f"/api/management/tiers/{tiers[0]['id']}", token=manager, json={
                "name": tiers[0]["name"], "rank": tiers[0]["rank"], "color": tiers[0]["color"],
                "min_points": tiers[0]["min_points"], "min_spend": tiers[0]["min_spend"],
                "points_multiplier": 2, "is_active": True,
            })
            assert tier["points_multiplier"] == 2

            design = await request(client, "GET", f"/api/wallet/design/{brand_id}", token=manager)
            design_payload = {key: design[key] for key in [
                "background_color", "foreground_color", "label_color", "logo_text", "card_title",
                "logo_url", "hero_url", "barcode_format", "fields", "terms",
            ]}
            await request(client, "PUT", f"/api/wallet/design/{brand_id}", token=manager, json=design_payload)
            await request(client, "POST", f"/api/wallet/design/{brand_id}/publish", token=manager, expected=409)

            await request(client, "POST", "/api/notifications/campaigns", token=manager, expected=422, json={
                "brand_id": brand_id, "name": "Wrong branch", "title": "No", "body": "No",
                "channel": "in_app", "audience_type": "branch",
                "audience_filter": {"branch_id": other_branch["id"]}, "recurrence": "none", "send_now": True,
            })
            branch_campaign = await deliver_campaign(client, manager, brand_id, {
                "brand_id": brand_id, "name": "West Bay", "title": "Branch", "body": "West Bay only",
                "channel": "in_app", "audience_type": "branch",
                "audience_filter": {"branch_id": branch["id"]}, "recurrence": "none", "send_now": True,
            })
            assert branch_campaign["status"] == "completed" and branch_campaign["sent_count"] == 1
            selected_campaign = await deliver_campaign(client, manager, brand_id, {
                "brand_id": brand_id, "name": "Selected", "title": "Selected", "body": "Mona only",
                "channel": "in_app", "audience_type": "selected",
                "audience_filter": {"customer_ids": [second_customer["id"]]}, "recurrence": "none", "send_now": True,
            })
            assert selected_campaign["status"] == "completed" and selected_campaign["sent_count"] == 1
            rewards_campaign = await deliver_campaign(client, manager, brand_id, {
                "brand_id": brand_id, "name": "Rewards", "title": "Reward ready", "body": "Redeem now",
                "channel": "in_app", "audience_type": "rewards_ready",
                "audience_filter": {}, "recurrence": "none", "send_now": True,
            })
            assert rewards_campaign["status"] == "completed" and rewards_campaign["sent_count"] == 1
            campaign = await deliver_campaign(client, manager, brand_id, {
                "brand_id": brand_id, "name": "Welcome", "title": "Hello", "body": "Welcome",
                "channel": "in_app", "audience_type": "all", "audience_filter": {},
                "recurrence": "none", "send_now": True,
            })
            assert campaign["status"] == "completed" and campaign["sent_count"] == 2
            inbox = await request(client, "GET", f"/api/notifications/inbox/{customer['membership_code']}")
            second_inbox = await request(client, "GET", f"/api/notifications/inbox/{second_customer['membership_code']}")
            assert len(inbox) == 3 and len(second_inbox) == 2
            audit = await request(client, "GET", f"/api/management/audit?brand_id={brand_id}", token=manager)
            assert len(audit) >= 10

            print(json.dumps({
                "ok": True, "brands": 2, "manager_brand_access": 2, "customer": customer_id,
                "coupon": coupon["code"], "campaign": campaign["status"], "audit_entries": len(audit),
                "security_checks": ["tenant_isolation", "central_wallet_forbidden", "password_preserved", "cross_branch_rejected", "campaign_audience_isolation"],
            }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
