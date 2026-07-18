"""End-to-end QA for Loyalyn V5 card templates, multi-program cards and safe reversal."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

DB = "/tmp/loyalyn-v5-cards-qa.db"
Path(DB).unlink(missing_ok=True)
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB}",
    "BOOTSTRAP_ADMIN_EMAIL": "owner-v5@example.com",
    "BOOTSTRAP_ADMIN_PASSWORD": "OwnerPass123!",
    "JWT_SECRET": "x" * 64,
    "ENCRYPTION_KEY": "y" * 64,
    "WALLET_STORAGE_DIR": "/tmp/loyalyn-v5-wallet-qa",
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
    if response.status_code == 204 or not response.content:
        return None
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
            owner = await login(client, "owner-v5@example.com", "OwnerPass123!")
            created = await request(client, "POST", "/api/brands", token=owner, expected=201, json={
                "name": "ONA V5", "slug": "ona-v5", "primary_color": "#70050B",
                "accent_color": "#C6FF4A", "currency": "QAR", "timezone": "Asia/Qatar", "locale": "ar",
                "program_mode": "stamps_only", "manager_name": "ONA Manager",
                "manager_email": "manager-v5@example.com", "manager_password": "ManagerPass123!",
            })
            brand_id = created["brand"]["id"]
            manager = await login(client, "manager-v5@example.com", "ManagerPass123!")

            programs = await request(client, "GET", f"/api/stamps/programs?brand_id={brand_id}", token=manager)
            coffee = await request(client, "PATCH", f"/api/stamps/programs/{programs[0]['id']}", token=manager, json={
                "name": "قهوة", "slug": "coffee", "required_stamps": 6,
                "reward_title": "مشروب مجاني", "stamp_icon": "coffee",
            })
            sweet = await request(client, "POST", "/api/stamps/programs", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "حلى", "slug": "sweet", "description": "حلويات",
                "required_stamps": 5, "reward_title": "حلى مجاني", "reward_type": "free_item",
                "stamp_icon": "cake", "background_color": "#40192A", "accent_color": "#FFB6C1",
                "is_default": False, "sort_order": 2, "is_active": True,
            })
            breakfast = await request(client, "POST", "/api/stamps/programs", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "فطور", "slug": "breakfast", "description": None,
                "required_stamps": 4, "reward_title": "فطور مجاني", "reward_type": "free_item",
                "stamp_icon": "star", "background_color": "#152238", "accent_color": "#F5C451",
                "is_default": False, "sort_order": 3, "is_active": True,
            })

            coffee_only = await request(client, "POST", "/api/cards/templates", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "قهوة فقط", "name_en": "Coffee Only", "slug": "coffee-only",
                "description": "بطاقة القهوة", "is_default": False, "allow_public_join": True,
                "sort_order": 10, "program_ids": [coffee["id"]], "background_color": "#28110D",
                "foreground_color": "#FFFFFF", "label_color": "#C6FF4A", "logo_text": "ona",
                "card_title": "بطاقة القهوة", "layout_style": "classic", "overlay_opacity": 25,
                "barcode_format": "PKBarcodeFormatQR", "fields": {"show_stamps": True, "show_rewards": True},
            })
            combo = await request(client, "POST", "/api/cards/templates", token=manager, expected=201, json={
                "brand_id": brand_id, "name": "قهوة وحلى", "name_en": "Coffee & Sweet", "slug": "coffee-sweet",
                "description": "بطاقة واحدة ببرنامجين", "is_default": True, "allow_public_join": True,
                "sort_order": 1, "program_ids": [coffee["id"], sweet["id"]], "background_color": "#70050B",
                "foreground_color": "#FFFFFF", "label_color": "#C6FF4A", "logo_text": "ona",
                "card_title": "بطاقة الولاء", "layout_style": "visual", "overlay_opacity": 30,
                "barcode_format": "PKBarcodeFormatQR", "fields": {"show_stamps": True, "show_rewards": True},
            })
            coffee_only = await request(client, "POST", f"/api/cards/templates/{coffee_only['id']}/publish", token=manager)
            combo = await request(client, "POST", f"/api/cards/templates/{combo['id']}/publish", token=manager)
            assert combo["status"] == "published" and combo["program_ids"] == [coffee["id"], sweet["id"]]

            public_profile = await request(client, "GET", "/api/public/brands/ona-v5")
            public_templates = {x["slug"]: x for x in public_profile["card_templates"]}
            assert {"coffee-only", "coffee-sweet"}.issubset(public_templates)
            assert [x["slug"] for x in public_templates["coffee-sweet"]["programs"]] == ["coffee", "sweet"]

            # Draft changes must not leak to public or existing Wallet cards before publish.
            await request(client, "PATCH", f"/api/cards/templates/{combo['id']}", token=manager, json={
                "name": "قهوة فقط - تعديل غير منشور", "program_ids": [coffee["id"]],
            })
            public_before_publish = await request(client, "GET", "/api/public/brands/ona-v5")
            public_combo = next(x for x in public_before_publish["card_templates"] if x["slug"] == "coffee-sweet")
            assert public_combo["name"] == "قهوة وحلى"
            assert [x["slug"] for x in public_combo["programs"]] == ["coffee", "sweet"]
            # Restore draft to intended combo and publish.
            await request(client, "PATCH", f"/api/cards/templates/{combo['id']}", token=manager, json={
                "name": "قهوة وحلى", "program_ids": [coffee["id"], sweet["id"]],
            })
            await request(client, "POST", f"/api/cards/templates/{combo['id']}/publish", token=manager)

            joined = await request(client, "POST", "/api/public/brands/ona-v5/join", expected=201, json={
                "name": "Ahmed", "phone": "55550001", "email": None, "birthday": None,
                "selected_card_template_id": combo["id"],
            })
            customer_id = joined["customer"]["id"]
            code = joined["customer"]["membership_code"]
            assert joined["card_template"]["slug"] == "coffee-sweet"
            assert [x["slug"] for x in joined["cards"]] == ["coffee", "sweet"]

            scan = await request(client, "GET", f"/api/stamps/scan/{code}?brand_id={brand_id}", token=manager)
            assert scan["card_template"]["slug"] == "coffee-sweet"
            assert [x["slug"] for x in scan["cards"]] == ["coffee", "sweet"]

            # An employee cannot add a program that is not part of the customer's selected card.
            await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{breakfast['id']}/add", token=manager, expected=409, json={
                "quantity": 1, "branch_id": None, "idempotency_key": "breakfast-not-assigned",
            })

            added = await request(client, "POST", f"/api/stamps/customers/{customer_id}/programs/{coffee['id']}/add", token=manager, json={
                "quantity": 1, "branch_id": None, "idempotency_key": "coffee-add-v5",
            })
            assert next(x for x in added["cards"] if x["slug"] == "coffee")["stamps"] == 1
            transactions = await request(client, "GET", f"/api/stamps/transactions?brand_id={brand_id}&customer_id={customer_id}", token=manager)
            original = transactions[0]
            reversed_result = await request(client, "POST", f"/api/stamps/transactions/{original['id']}/reverse", token=manager, json={
                "reason": "تمت الإضافة بالخطأ", "idempotency_key": "reverse-coffee-v5",
            })
            assert next(x for x in reversed_result["cards"] if x["slug"] == "coffee")["stamps"] == 0
            await request(client, "POST", f"/api/stamps/transactions/{original['id']}/reverse", token=manager, expected=409, json={
                "reason": "تكرار", "idempotency_key": "reverse-coffee-v5-second",
            })

            # Change the customer's one main card to a different template.
            assignment = await request(client, "PUT", f"/api/cards/customers/{customer_id}/assignment", token=manager, json={
                "card_template_id": coffee_only["id"],
            })
            assert assignment["card_template"]["slug"] == "coffee-only"
            scan_after_assignment = await request(client, "GET", f"/api/stamps/scan/{code}?brand_id={brand_id}", token=manager)
            assert [x["slug"] for x in scan_after_assignment["cards"]] == ["coffee"]

            duplicate = await request(client, "POST", f"/api/cards/templates/{combo['id']}/duplicate", token=manager, expected=201)
            await request(client, "POST", f"/api/cards/templates/{duplicate['id']}/archive", token=manager)
            await request(client, "POST", f"/api/cards/templates/{duplicate['id']}/restore", token=manager)
            await request(client, "DELETE", f"/api/cards/templates/{duplicate['id']}", token=manager, expected=204)

            print(json.dumps({
                "ok": True,
                "version": "6.0.0",
                "one_main_card_per_customer": True,
                "multiple_stamp_programs_in_one_card": True,
                "multiple_card_templates": True,
                "draft_publish_isolation": True,
                "safe_stamp_reversal": True,
                "archive_restore_safe_delete": True,
                "program_scope_enforced": True,
            }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
