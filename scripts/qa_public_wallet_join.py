"""End-to-end public join -> real .pkpass delivery test for Loyalyn 6.0.0."""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

DB = "/tmp/loyalyn-v411-public-wallet.db"
Path(DB).unlink(missing_ok=True)
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB}",
    "BOOTSTRAP_ADMIN_EMAIL": "owner-wallet@example.com",
    "BOOTSTRAP_ADMIN_PASSWORD": "OwnerPass123!",
    "JWT_SECRET": "x" * 64,
    "ENCRYPTION_KEY": "y" * 64,
    "WALLET_STORAGE_DIR": "/tmp/loyalyn-v411-wallet-data",
    "PUBLIC_API_URL": "https://api.example.com",
    "PUBLIC_WEB_URL": "https://app.example.com",
})

import httpx
from app.db.session import engine
from app.main import app
from app.models import Base


def run(*args: str) -> None:
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
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json(), response
    return response.content, response


async def login(client, email, password):
    data, _ = await request(client, "POST", "/api/auth/login", json={"email": email, "password": password})
    return data["access_token"]


async def main():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    with tempfile.TemporaryDirectory(prefix="loyalyn-wallet-qa-") as temp:
        temp_path = Path(temp)
        pass_type = "pass.com.loyalyn.publicqa"
        team_id = "TEAM123456"
        password = "wallet-test-password"
        signer_key = temp_path / "signer.key"
        signer_cert = temp_path / "signer.pem"
        p12 = temp_path / "wallet.p12"
        wwdr_key = temp_path / "wwdr.key"
        wwdr = temp_path / "wwdr.pem"
        run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30", "-keyout", str(signer_key), "-out", str(signer_cert), "-subj", f"/CN=Loyalyn Public QA/OU={team_id}/UID={pass_type}")
        run("openssl", "pkcs12", "-export", "-out", str(p12), "-inkey", str(signer_key), "-in", str(signer_cert), "-passout", f"pass:{password}")
        run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30", "-keyout", str(wwdr_key), "-out", str(wwdr), "-subj", "/CN=QA WWDR/O=Apple QA")

        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                owner = await login(client, "owner-wallet@example.com", "OwnerPass123!")
                created, _ = await request(client, "POST", "/api/brands", token=owner, expected=201, json={
                    "name": "Wallet Coffee", "slug": "wallet-coffee", "primary_color": "#70050B",
                    "accent_color": "#C6FF4A", "currency": "QAR", "timezone": "Asia/Qatar", "locale": "ar",
                    "program_mode": "stamps_only", "manager_name": "Wallet Manager",
                    "manager_email": "wallet-manager@example.com", "manager_password": "ManagerPass123!",
                })
                brand_id = created["brand"]["id"]
                manager = await login(client, "wallet-manager@example.com", "ManagerPass123!")

                # Before platform setup, joining still gets a stable card page but no fake Wallet action.
                pending, _ = await request(client, "POST", "/api/public/brands/wallet-coffee/join", expected=201, json={
                    "name": "Pending Customer", "phone": "50000001", "email": None, "birthday": None,
                    "selected_program_ids": [],
                })
                assert pending["wallet"]["status"] == "certificate_not_configured"
                assert pending["wallet"]["card_url"]
                assert pending["wallet"]["download_url"] is None

                with p12.open("rb") as p12_handle, wwdr.open("rb") as wwdr_handle:
                    uploaded, _ = await request(
                        client, "POST", "/api/wallet/platform/credential", token=owner, expected=201,
                        data={
                            "password": password,
                            "pass_type_identifier": pass_type,
                            "team_identifier": team_id,
                            "organization_name": "Loyalyn QA",
                        },
                        files={
                            "p12_file": ("wallet.p12", p12_handle, "application/x-pkcs12"),
                            "wwdr_file": ("wwdr.pem", wwdr_handle, "application/x-pem-file"),
                        },
                    )
                assert uploaded["configured"] is True
                await request(client, "POST", f"/api/wallet/design/{brand_id}/publish", token=manager)

                joined, _ = await request(client, "POST", "/api/public/brands/wallet-coffee/join", expected=201, json={
                    "name": "Ahmed", "phone": "50000002", "email": None, "birthday": None,
                    "selected_program_ids": [],
                })
                assert joined["wallet"]["ready"] is True
                assert joined["wallet"]["status"] == "ready"
                assert joined["wallet"]["card_url"].startswith("https://app.example.com/card/")
                assert joined["wallet"]["download_url"].endswith(".pkpass")

                pkpass_path = urlparse(joined["wallet"]["download_url"]).path
                payload, response = await request(client, "GET", pkpass_path)
                assert payload.startswith(b"PK")
                assert response.headers["content-type"].startswith("application/vnd.apple.pkpass")
                assert response.headers["x-content-type-options"] == "nosniff"
                assert "no-store" in response.headers["cache-control"]

                card_path = urlparse(joined["wallet"]["card_url"]).path.replace("/card/", "/api/wallet/public/card/")
                public_card, _ = await request(client, "GET", card_path)
                assert public_card["wallet"]["ready"] is True
                assert public_card["download_url"].endswith(".pkpass")

                print({
                    "ok": True,
                    "version": "6.0.0",
                    "pending_state_is_explicit": True,
                    "stable_card_url_before_setup": True,
                    "join_returns_real_pkpass_after_setup": True,
                    "pkpass_mime_type": response.headers["content-type"],
                })


if __name__ == "__main__":
    asyncio.run(main())
