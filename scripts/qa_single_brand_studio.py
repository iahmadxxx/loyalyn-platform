"""End-to-end QA for Loyalyn V6 single-brand multi-card stamp studio."""
from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

DB = "/tmp/loyalyn-v6-studio-qa.db"
Path(DB).unlink(missing_ok=True)
WALLET_DIR = "/tmp/loyalyn-v6-studio-wallet"
subprocess.run(["rm", "-rf", WALLET_DIR], check=False)
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB}",
    "BOOTSTRAP_ADMIN_EMAIL": "owner-v6@example.com",
    "BOOTSTRAP_ADMIN_PASSWORD": "OwnerPass123!",
    "JWT_SECRET": "x" * 64,
    "ENCRYPTION_KEY": "y" * 64,
    "WALLET_STORAGE_DIR": WALLET_DIR,
    "PUBLIC_API_URL": "https://api.example.com",
    "PUBLIC_WEB_URL": "https://app.example.com",
})

import httpx
from PIL import Image, ImageDraw
from app.db.session import engine
from app.main import app
from app.models import Base


def shell(*args: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


async def request(client, method, path, *, token=None, expected=200, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.request(method, path, headers=headers, **kwargs)
    if response.status_code != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {response.status_code}: {response.text}")
    if response.status_code == 204 or not response.content:
        return None, response
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json(), response
    return response.content, response


async def login(client, email, password):
    data, _ = await request(client, "POST", "/api/auth/login", json={"email": email, "password": password})
    return data["access_token"]


def program_payload(brand_id: str, name: str, slug: str, icon: str, required: int):
    return {
        "brand_id": brand_id, "name": name, "slug": slug, "description": "",
        "required_stamps": required, "reward_title": f"مكافأة {name}", "reward_type": "free_item",
        "stamp_icon": icon, "background_color": "#A79889", "accent_color": "#5B4033",
        "display_options": {"icon_size": 46, "gap": 8, "offset_x": 0, "offset_y": 0, "fit": "contain", "shape": "none", "empty_opacity": 35},
        "is_default": False, "sort_order": 0, "is_active": True,
    }


def card_payload(brand_id: str, name: str, slug: str, program_ids: list[str], order: int):
    return {
        "brand_id": brand_id, "name": name, "name_en": "", "slug": slug, "description": "",
        "is_default": order == 0, "allow_public_join": True, "sort_order": order,
        "program_ids": program_ids, "background_color": "#A79889", "foreground_color": "#FFFFFF",
        "label_color": "#FFFFFF", "logo_text": "ONA", "card_title": "بطاقة الولاء",
        "layout_style": "visual", "overlay_opacity": 15, "barcode_format": "PKBarcodeFormatQR",
        "fields": {
            "show_stamps": True, "show_rewards": True, "show_points": False, "show_tier": False,
            "show_visits": False, "render_stamp_strip": True, "stamp_panel_color": "#FFFFFF",
            "stamp_panel_text_color": "#756B63", "stamp_panel_title": "LOYALTY CARD",
        },
        "terms": "",
    }


async def main():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    with tempfile.TemporaryDirectory(prefix="loyalyn-v6-cert-") as temp:
        temp_path = Path(temp)
        pass_type = "pass.com.loyalyn.v6qa"
        team_id = "TEAM123456"
        password = "wallet-test-password"
        signer_key = temp_path / "signer.key"
        signer_cert = temp_path / "signer.pem"
        p12 = temp_path / "wallet.p12"
        wwdr_key = temp_path / "wwdr.key"
        wwdr = temp_path / "wwdr.pem"
        shell("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30", "-keyout", str(signer_key), "-out", str(signer_cert), "-subj", f"/CN=Loyalyn V6 QA/OU={team_id}/UID={pass_type}")
        shell("openssl", "pkcs12", "-export", "-out", str(p12), "-inkey", str(signer_key), "-in", str(signer_cert), "-passout", f"pass:{password}")
        shell("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30", "-keyout", str(wwdr_key), "-out", str(wwdr), "-subj", "/CN=QA WWDR/O=Apple QA")

        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                owner = await login(client, "owner-v6@example.com", "OwnerPass123!")
                created, _ = await request(client, "POST", "/api/brands", token=owner, expected=201, json={
                    "name": "ONA", "slug": "ona-v6", "primary_color": "#A79889", "accent_color": "#FFFFFF",
                    "currency": "QAR", "timezone": "Asia/Qatar", "locale": "ar", "program_mode": "stamps_only",
                    "manager_name": "ONA Manager", "manager_email": "manager-v6@example.com", "manager_password": "ManagerPass123!",
                })
                brand_id = created["brand"]["id"]
                manager = await login(client, "manager-v6@example.com", "ManagerPass123!")

                with p12.open("rb") as p12_handle, wwdr.open("rb") as wwdr_handle:
                    await request(client, "POST", "/api/wallet/platform/credential", token=owner, expected=201,
                        data={"password": password, "pass_type_identifier": pass_type, "team_identifier": team_id, "organization_name": "ONA"},
                        files={"p12_file": ("wallet.p12", p12_handle, "application/x-pkcs12"), "wwdr_file": ("wwdr.pem", wwdr_handle, "application/x-pem-file")})

                created_programs = {}
                for key, name, slug, icon, required in [
                    ("coffee", "قهوة", "coffee-v6", "coffee", 7),
                    ("sweet", "حلى", "sweet-v6", "cake", 5),
                    ("combo_coffee", "قهوة", "combo-coffee-v6", "coffee", 7),
                    ("combo_sweet", "حلى", "combo-sweet-v6", "cake", 5),
                ]:
                    row, _ = await request(client, "POST", "/api/stamps/programs", token=manager, expected=201,
                                           json=program_payload(brand_id, name, slug, icon, required))
                    created_programs[key] = row

                # Upload an intentionally oversized transparent stamp logo. The renderer must contain it in a fixed slot.
                stamp_image = Image.new("RGBA", (420, 180), (0, 0, 0, 0))
                draw = ImageDraw.Draw(stamp_image)
                draw.rounded_rectangle((10, 10, 410, 170), radius=60, fill=(96, 50, 35, 255))
                draw.ellipse((170, 35, 250, 115), fill=(255, 255, 255, 255))
                raw = io.BytesIO(); stamp_image.save(raw, format="PNG")
                await request(client, "POST", f"/api/stamps/programs/{created_programs['combo_coffee']['id']}/asset", token=manager,
                              data={"kind": "filled_stamp"}, files={"file": ("wide-logo.png", raw.getvalue(), "image/png")})

                templates = {}
                for key, name, slug, ids, order in [
                    ("coffee", "بطاقة القهوة", "coffee-card-v6", [created_programs["coffee"]["id"]], 0),
                    ("sweet", "بطاقة الحلى", "sweet-card-v6", [created_programs["sweet"]["id"]], 1),
                    ("combo", "بطاقة القهوة والحلى", "combo-card-v6", [created_programs["combo_coffee"]["id"], created_programs["combo_sweet"]["id"]], 2),
                ]:
                    card, _ = await request(client, "POST", "/api/cards/templates", token=manager, expected=201,
                                            json=card_payload(brand_id, name, slug, ids, order))
                    card, _ = await request(client, "POST", f"/api/cards/templates/{card['id']}/publish", token=manager)
                    templates[key] = card

                registered, _ = await request(client, "POST", "/api/public/brands/ona-v6/join", expected=201, json={
                    "name": "Public Member", "phone": "55550000", "email": None, "birthday": None,
                })
                assert registered["wallet"]["status"] == "assignment_pending"
                assert registered["card_template"] is None and registered["download_url"] is None

                customer, _ = await request(client, "POST", "/api/customers", token=manager, expected=201, json={
                    "brand_id": brand_id, "name": "Ali", "phone": "55551234", "email": None, "birthday": None,
                    "home_branch_id": None, "tags": [], "notes": None, "card_template_id": None,
                })
                customer_id = customer["id"]
                assignments, _ = await request(client, "GET", f"/api/cards/customers/{customer_id}/assignments", token=manager)
                assert assignments == [], assignments

                for template in templates.values():
                    await request(client, "POST", f"/api/cards/customers/{customer_id}/assignments/{template['id']}", token=manager, expected=201)

                assignments, _ = await request(client, "GET", f"/api/cards/customers/{customer_id}/assignments", token=manager)
                assert len(assignments) == 3
                assert {x["card_template"]["slug"] for x in assignments} == {"coffee-card-v6", "sweet-card-v6", "combo-card-v6"}

                scan, _ = await request(client, "GET", f"/api/stamps/scan/{customer['membership_code']}?brand_id={brand_id}", token=manager)
                assert len(scan["card_templates"]) == 3
                assert {x["slug"] for x in scan["card_templates"]} == {"coffee-card-v6", "sweet-card-v6", "combo-card-v6"}
                combo_group = next(x for x in scan["card_templates"] if x["slug"] == "combo-card-v6")
                assert [x["slug"] for x in combo_group["cards"]] == ["combo-coffee-v6", "combo-sweet-v6"]

                issued = []
                for template in templates.values():
                    result, _ = await request(client, "POST", f"/api/wallet/passes/{customer_id}/{template['id']}", token=manager, expected=201)
                    issued.append(result)
                assert len({x["card_url"] for x in issued}) == 3
                assert len({x["download_url"] for x in issued}) == 3

                pass_programs = {}
                for result in issued:
                    payload, response = await request(client, "GET", urlparse(result["download_url"]).path)
                    assert payload.startswith(b"PK")
                    assert response.headers["content-type"].startswith("application/vnd.apple.pkpass")
                    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                        names = set(archive.namelist())
                        assert {"pass.json", "strip.png", "strip@2x.png", "manifest.json", "signature"}.issubset(names)
                        pass_json = json.loads(archive.read("pass.json"))
                        labels = [x["label"] for x in pass_json["storeCard"]["secondaryFields"] if x["key"].startswith("stampCard")]
                        pass_programs[result["card_template_name"]] = labels
                        strip = Image.open(io.BytesIO(archive.read("strip.png")))
                        assert strip.size == (375, 123)
                        strip2 = Image.open(io.BytesIO(archive.read("strip@2x.png")))
                        assert strip2.size == (750, 246)

                assert pass_programs["بطاقة القهوة"] == ["قهوة"]
                assert pass_programs["بطاقة الحلى"] == ["حلى"]
                assert pass_programs["بطاقة القهوة والحلى"] == ["قهوة", "حلى"]

                # Remove one card while keeping the other two active.
                await request(client, "DELETE", f"/api/cards/customers/{customer_id}/assignments/{templates['sweet']['id']}", token=manager, expected=204)
                assignments, _ = await request(client, "GET", f"/api/cards/customers/{customer_id}/assignments", token=manager)
                assert len(assignments) == 2
                assert {x["card_template"]["slug"] for x in assignments} == {"coffee-card-v6", "combo-card-v6"}

                # The one-screen customer editor can replace the complete active-card set, including zero cards.
                assignments, _ = await request(client, "PUT", f"/api/cards/customers/{customer_id}/assignments", token=manager, json={"card_template_ids": []})
                assert assignments == []
                assignments, _ = await request(client, "PUT", f"/api/cards/customers/{customer_id}/assignments", token=manager, json={
                    "card_template_ids": [templates["coffee"]["id"], templates["sweet"]["id"], templates["combo"]["id"]]
                })
                assert len(assignments) == 3

                print(json.dumps({
                    "ok": True,
                    "version": "6.0.0",
                    "single_brand_studio": True,
                    "customer_can_start_without_card": True,
                    "public_registration_then_manager_assignment": True,
                    "three_cards_active_together": True,
                    "coffee_sweet_combo_in_one_pass": True,
                    "separate_coffee_and_sweet_passes": True,
                    "custom_stamp_asset_fixed_strip": True,
                    "three_distinct_pkpass_files": True,
                }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
