import hashlib
import json
import secrets
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models import (
    Brand, BrandWalletDesign, CardTemplate, Customer, PlatformWalletCredential, WalletDevice,
    WalletPass, WalletRegistration,
)
from app.services.capabilities import brand_capabilities

settings = get_settings()


def _run(args: list[str], *, timeout: int = 30) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "OpenSSL operation failed").strip())
    return result.stdout.strip()


def normalize_wwdr(source: Path, destination: Path) -> None:
    try:
        _run(["openssl", "x509", "-in", str(source), "-out", str(destination)])
    except RuntimeError:
        _run(["openssl", "x509", "-inform", "DER", "-in", str(source), "-out", str(destination)])


def validate_and_extract_certificate(
    p12_path: Path,
    wwdr_source: Path,
    password: str,
    output_dir: Path,
    *,
    expected_pass_type_identifier: str | None = None,
    expected_team_identifier: str | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_path = output_dir / "signer.pem"
    key_path = output_dir / "signer.key"
    wwdr_path = output_dir / "wwdr.pem"
    _run(["openssl", "pkcs12", "-in", str(p12_path), "-clcerts", "-nokeys", "-passin", f"pass:{password}", "-out", str(cert_path)])
    _run(["openssl", "pkcs12", "-in", str(p12_path), "-nocerts", "-nodes", "-passin", f"pass:{password}", "-out", str(key_path)])
    normalize_wwdr(wwdr_source, wwdr_path)
    subject = _run(["openssl", "x509", "-in", str(cert_path), "-noout", "-subject", "-nameopt", "RFC2253"])
    cert_public_key = _run(["openssl", "x509", "-in", str(cert_path), "-pubkey", "-noout"])
    key_public_key = _run(["openssl", "pkey", "-in", str(key_path), "-pubout"])
    if "".join(cert_public_key.split()) != "".join(key_public_key.split()):
        raise RuntimeError("The private key does not match the Wallet certificate")
    if expected_pass_type_identifier and f"UID={expected_pass_type_identifier}" not in subject:
        raise RuntimeError("Pass Type Identifier does not match the uploaded certificate")
    if expected_team_identifier and f"OU={expected_team_identifier}" not in subject:
        raise RuntimeError("Team Identifier does not match the uploaded certificate")
    enddate = _run(["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"]).replace("notAfter=", "")
    expires_at = datetime.strptime(enddate, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise RuntimeError("Apple Wallet certificate is expired")
    wwdr_enddate = _run(["openssl", "x509", "-in", str(wwdr_path), "-noout", "-enddate"]).replace("notAfter=", "")
    wwdr_expires_at = datetime.strptime(wwdr_enddate, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    if wwdr_expires_at <= datetime.now(timezone.utc):
        raise RuntimeError("Apple WWDR certificate is expired")
    output_dir.chmod(0o700)
    for protected in (p12_path, cert_path, key_path, wwdr_path):
        protected.chmod(0o600)
    return {
        "certificate_subject": subject,
        "expires_at": expires_at,
        "cert_path": str(cert_path),
        "key_path": str(key_path),
        "wwdr_path": str(wwdr_path),
        "wwdr_expires_at": wwdr_expires_at,
    }


def credential_paths(credential: PlatformWalletCredential) -> tuple[Path, Path, Path]:
    folder = Path(credential.p12_path).parent
    return folder / "signer.pem", folder / "signer.key", Path(credential.wwdr_path)


def _rgb(value: str) -> str:
    raw = value.lstrip("#")
    if len(raw) != 6:
        raw = "111827"
    return f"rgb({int(raw[0:2],16)}, {int(raw[2:4],16)}, {int(raw[4:6],16)})"


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def make_icon(initial: str, background: str, foreground: str, size: int) -> bytes:
    image = Image.new("RGBA", (size, size), background)
    draw = ImageDraw.Draw(image)
    text = (initial or "L")[0].upper()
    font = _font(max(12, int(size * 0.55)))
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((size - (box[2] - box[0])) / 2, (size - (box[3] - box[1])) / 2 - box[1]), text, fill=foreground, font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()



def render_asset(source: str | None, size: tuple[int, int], *, contain: bool = True) -> bytes | None:
    if not source or not source.startswith("storage://"):
        return None
    path = Path(source.removeprefix("storage://"))
    if not path.exists():
        return None
    with Image.open(path) as image:
        image = image.convert("RGBA")
        if contain:
            image.thumbnail(size, Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            canvas.alpha_composite(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
            output_image = canvas
        else:
            output_image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        buffer = BytesIO()
        output_image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()


def build_pass_json(
    *, credential: PlatformWalletCredential, brand: Brand, customer: Customer,
    design: Any, wallet_pass: WalletPass,
) -> dict:
    fields = design.fields or {}
    primary = []
    secondary = []
    auxiliary = []
    if fields.get("show_points", True):
        primary.append({"key": "points", "label": fields.get("points_label", "النقاط"), "value": customer.points})
    if fields.get("show_rewards", True):
        secondary.append({"key": "rewards", "label": fields.get("rewards_label", "المكافآت"), "value": customer.available_rewards})
    if fields.get("show_stamps", True):
        secondary.append({"key": "stamps", "label": fields.get("stamps_label", "الأختام"), "value": customer.stamps})
    if fields.get("show_tier", True):
        auxiliary.append({"key": "tier", "label": fields.get("tier_label", "العضوية"), "value": customer.tier})
    if fields.get("show_visits", True):
        auxiliary.append({"key": "visits", "label": fields.get("visits_label", "الزيارات"), "value": customer.visits})
    back_fields = [
        {"key": "member", "label": "العميل", "value": customer.name},
        {"key": "memberCode", "label": "رقم العضوية", "value": customer.membership_code},
    ]
    stamp_cards = list(getattr(customer, "_wallet_stamp_cards", []) or [])
    if fields.get("show_stamps", True) and stamp_cards:
        # One Apple Wallet pass can represent several independent stamp
        # programs.  Apple controls the physical field layout, so the first
        # two programs are shown on the front, up to three more are shown in
        # auxiliary fields, and every program remains available on the back.
        primary = [{"key": "memberName", "label": "العضو", "value": customer.name}]
        secondary = [item for item in secondary if item.get("key") != "stamps"]
        stamp_front = [
            {
                "key": f"stampCard{index}",
                "label": card["name"],
                "value": f"{card['stamps']} / {card['required_stamps']}",
            }
            for index, card in enumerate(stamp_cards[:2])
        ]
        secondary = stamp_front + secondary[: max(0, 2 - len(stamp_front))]
        extra_stamp_fields = [
            {
                "key": f"stampExtra{index}",
                "label": card["name"],
                "value": f"{card['stamps']} / {card['required_stamps']}",
            }
            for index, card in enumerate(stamp_cards[2:5], start=2)
        ]
        auxiliary = extra_stamp_fields + auxiliary[: max(0, 3 - len(extra_stamp_fields))]
        for index, card in enumerate(stamp_cards):
            ready_text = f" · مكافآت جاهزة: {card['rewards_available']}" if card["rewards_available"] else ""
            back_fields.append({
                "key": f"stampProgram{index}", "label": card["name"],
                "value": f"{card['stamps']} من {card['required_stamps']}{ready_text}",
            })
    if design.terms:
        back_fields.append({"key": "terms", "label": "الشروط والأحكام", "value": design.terms})
    return {
        "formatVersion": 1,
        "passTypeIdentifier": credential.pass_type_identifier,
        "serialNumber": wallet_pass.serial_number,
        "teamIdentifier": credential.team_identifier,
        "organizationName": credential.organization_name,
        "description": f"{brand.name} Loyalty Card",
        "logoText": design.logo_text or brand.name,
        "foregroundColor": _rgb(design.foreground_color),
        "backgroundColor": _rgb(design.background_color),
        "labelColor": _rgb(design.label_color),
        "webServiceURL": f"{settings.public_api_url.rstrip('/')}/api/wallet",
        "authenticationToken": wallet_pass.authentication_token,
        "barcodes": [{
            "format": design.barcode_format,
            "message": customer.membership_code,
            "messageEncoding": "iso-8859-1",
            "altText": customer.membership_code,
        }],
        "storeCard": {
            "headerFields": [{"key": "brand", "label": "", "value": brand.name}],
            "primaryFields": primary,
            "secondaryFields": secondary,
            "auxiliaryFields": auxiliary,
            "backFields": back_fields,
        },
    }


def generate_pkpass_bytes(
    *, credential: PlatformWalletCredential, brand: Brand, customer: Customer,
    design: Any, wallet_pass: WalletPass,
) -> bytes:
    cert_path, key_path, wwdr_path = credential_paths(credential)
    for required in (cert_path, key_path, wwdr_path):
        if not required.exists():
            raise RuntimeError("Wallet signing files are missing. Upload the certificate again.")
    with tempfile.TemporaryDirectory(prefix="loyalyn-pass-") as temp:
        root = Path(temp)
        pass_json = build_pass_json(credential=credential, brand=brand, customer=customer, design=design, wallet_pass=wallet_pass)
        (root / "pass.json").write_text(json.dumps(pass_json, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (root / "icon.png").write_bytes(make_icon(brand.name, design.background_color, design.foreground_color, 29))
        (root / "icon@2x.png").write_bytes(make_icon(brand.name, design.background_color, design.foreground_color, 58))
        logo = render_asset(design.logo_url, (160, 50), contain=True)
        logo2 = render_asset(design.logo_url, (320, 100), contain=True)
        (root / "logo.png").write_bytes(logo or make_icon(brand.name, design.background_color, design.foreground_color, 80))
        (root / "logo@2x.png").write_bytes(logo2 or make_icon(brand.name, design.background_color, design.foreground_color, 160))
        strip_source = getattr(design, "strip_url", None) or design.hero_url or getattr(design, "background_image_url", None)
        strip = render_asset(strip_source, (375, 123), contain=False)
        strip2 = render_asset(strip_source, (750, 246), contain=False)
        if strip and strip2:
            (root / "strip.png").write_bytes(strip)
            (root / "strip@2x.png").write_bytes(strip2)
        manifest = {}
        for file in root.iterdir():
            if file.name not in {"manifest.json", "signature"} and file.is_file():
                manifest[file.name] = hashlib.sha1(file.read_bytes()).hexdigest()
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
        _run([
            "openssl", "smime", "-binary", "-sign", "-certfile", str(wwdr_path),
            "-signer", str(cert_path), "-inkey", str(key_path), "-in", str(manifest_path),
            "-out", str(root / "signature"), "-outform", "DER",
        ])
        output = BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in root.iterdir():
                if file.is_file():
                    archive.write(file, file.name)
        return output.getvalue()


def public_wallet_status(
    *,
    brand: Brand,
    design: BrandWalletDesign | None,
    credential: PlatformWalletCredential | None,
    card_template: CardTemplate | None = None,
) -> dict:
    """Return a stable public status for the customer Wallet journey.

    The public UI must never present the membership QR as if it were the
    Apple Wallet pass.  These explicit states let it show the correct call to
    action and a useful setup message when signing is not ready yet.
    """
    if not brand_capabilities(brand).get("wallet"):
        return {
            "ready": False,
            "status": "disabled",
            "message": "ميزة Apple Wallet غير مفعلة لهذا البراند.",
        }
    if not credential:
        return {
            "ready": False,
            "status": "certificate_not_configured",
            "message": "تم إنشاء عضويتك، لكن شهادة Apple Wallet المركزية لم تُجهز بعد.",
        }
    if card_template is not None:
        if card_template.status != "published":
            return {
                "ready": False,
                "status": "card_template_not_published",
                "message": "تم إنشاء عضويتك، لكن بطاقة البراند المختارة لم تُنشر بعد.",
            }
    else:
        if not design:
            return {
                "ready": False,
                "status": "design_missing",
                "message": "تم إنشاء عضويتك، لكن تصميم بطاقة Apple Wallet لم يُجهز بعد.",
            }
        if not design.is_published:
            return {
                "ready": False,
                "status": "design_not_published",
                "message": "تم إنشاء عضويتك، لكن مدير البراند لم ينشر تصميم البطاقة بعد.",
            }
    return {
        "ready": True,
        "status": "ready",
        "message": "بطاقتك جاهزة للإضافة إلى Apple Wallet.",
    }


async def active_credential(db: AsyncSession) -> PlatformWalletCredential | None:
    return await db.scalar(
        select(PlatformWalletCredential).where(
            PlatformWalletCredential.is_active.is_(True),
            PlatformWalletCredential.status == "active",
        ).order_by(PlatformWalletCredential.created_at.desc())
    )


async def push_pass_update(db: AsyncSession, wallet_pass: WalletPass) -> dict:
    credential = await active_credential(db)
    if not credential:
        return {"sent": 0, "failed": 0, "reason": "wallet_not_configured"}
    cert_path, key_path, _ = credential_paths(credential)
    rows = (
        await db.execute(
            select(WalletDevice).join(WalletRegistration, WalletRegistration.device_id == WalletDevice.id).where(
                WalletRegistration.pass_id == wallet_pass.id,
                WalletDevice.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not rows:
        return {"sent": 0, "failed": 0, "reason": "no_registered_devices"}
    sent = failed = 0
    async with httpx.AsyncClient(http2=True, timeout=15, cert=(str(cert_path), str(key_path))) as client:
        for device in rows:
            try:
                response = await client.post(
                    f"https://api.push.apple.com/3/device/{device.push_token}",
                    headers={
                        "apns-topic": credential.pass_type_identifier,
                        "apns-push-type": "background",
                        "apns-priority": "10",
                    },
                    json={},
                )
                if response.status_code == 200:
                    sent += 1
                else:
                    failed += 1
                    if response.status_code in {400, 410}:
                        device.is_active = False
            except Exception:
                failed += 1
    wallet_pass.last_push_at = datetime.now(timezone.utc)
    return {"sent": sent, "failed": failed}
