"""Verify that the Loyalyn v3 Alembic migration preserves the legacy MVP data.

Runs only against an isolated SQLite database under /tmp.
Usage from repository root:
    PYTHONPATH=backend python scripts/qa_legacy_migration.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

DB_PATH = Path('/tmp/loyalyn-v3-legacy-migration.db')
DB_PATH.unlink(missing_ok=True)
brand_id = uuid.uuid4()
owner_id = uuid.uuid4()
manager_id = uuid.uuid4()
customer_id = uuid.uuid4()
program_id = uuid.uuid4()
now = '2026-07-18 00:00:00.000000'

schema = """
CREATE TABLE brands (
 id CHAR(32) PRIMARY KEY, name VARCHAR(120) NOT NULL, slug VARCHAR(80) NOT NULL UNIQUE,
 logo_url TEXT, primary_color VARCHAR(7) NOT NULL, accent_color VARCHAR(7) NOT NULL,
 is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE users (
 id CHAR(32) PRIMARY KEY, email VARCHAR(190) NOT NULL UNIQUE, full_name VARCHAR(120) NOT NULL,
 password_hash VARCHAR(255) NOT NULL, role VARCHAR(30) NOT NULL, brand_id CHAR(32),
 is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
CREATE TABLE customers (
 id CHAR(32) PRIMARY KEY, brand_id CHAR(32) NOT NULL, name VARCHAR(120) NOT NULL,
 phone VARCHAR(32) NOT NULL, email VARCHAR(190), membership_code VARCHAR(64) NOT NULL UNIQUE,
 points INTEGER NOT NULL, stamps INTEGER NOT NULL, available_rewards INTEGER NOT NULL,
 tier VARCHAR(30) NOT NULL, visits INTEGER NOT NULL, is_active BOOLEAN NOT NULL,
 created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
 CONSTRAINT uq_customer_brand_phone UNIQUE (brand_id, phone)
);
CREATE TABLE loyalty_programs (
 id CHAR(32) PRIMARY KEY, brand_id CHAR(32) NOT NULL UNIQUE, program_type VARCHAR(30) NOT NULL,
 required_stamps INTEGER NOT NULL, points_per_visit INTEGER NOT NULL, reward_points INTEGER NOT NULL,
 reward_title VARCHAR(160) NOT NULL, rules JSON NOT NULL,
 created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
);
"""
with sqlite3.connect(DB_PATH) as db:
    db.executescript(schema)
    db.execute('INSERT INTO brands VALUES (?,?,?,?,?,?,?,?,?)', (
        brand_id.hex, 'Legacy Coffee', 'legacy-coffee', None, '#111827', '#C6FF4A', 1, now, now,
    ))
    db.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)', [
        (owner_id.hex, 'owner@legacy.test', 'Owner', 'x', 'owner', None, 1, now, now),
        (manager_id.hex, 'manager@legacy.test', 'Manager', 'x', 'manager', brand_id.hex, 1, now, now),
    ])
    db.execute('INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
        customer_id.hex, brand_id.hex, 'Legacy Customer', '55511111', 'legacy@test.com',
        'LEGACY-CODE', 40, 2, 0, 'bronze', 3, 1, now, now,
    ))
    db.execute('INSERT INTO loyalty_programs VALUES (?,?,?,?,?,?,?,?,?,?)', (
        program_id.hex, brand_id.hex, 'hybrid', 6, 10, 100, 'Free', '{}', now, now,
    ))
    db.commit()

env = os.environ.copy()
env['DATABASE_URL'] = f'sqlite+aiosqlite:///{DB_PATH}'
subprocess.run(
    ['alembic', 'upgrade', 'head'], cwd=Path(__file__).resolve().parents[1] / 'backend',
    env=env, check=True,
)
os.environ['DATABASE_URL'] = env['DATABASE_URL']

from sqlalchemy import func, select
from app.db.session import AsyncSessionLocal
from app.models import BrandWalletDesign, Customer, LoyaltyProgram, MembershipTier, User, UserBrandAccess


async def verify() -> None:
    async with AsyncSessionLocal() as db:
        users = list((await db.scalars(select(User).order_by(User.email))).all())
        assert [(u.email, u.role) for u in users] == [
            ('manager@legacy.test', 'brand_admin'), ('owner@legacy.test', 'platform_owner')
        ]
        customer = await db.scalar(select(Customer).where(Customer.membership_code == 'LEGACY-CODE'))
        assert customer and customer.points == 40 and customer.home_branch_id is None
        assert int(await db.scalar(select(func.count()).select_from(UserBrandAccess)) or 0) == 1
        assert int(await db.scalar(select(func.count()).select_from(BrandWalletDesign)) or 0) == 1
        assert int(await db.scalar(select(func.count()).select_from(MembershipTier)) or 0) == 4
        assert int(await db.scalar(select(func.count()).select_from(LoyaltyProgram)) or 0) == 1
        print({
            'migration': 'ok',
            'users': [(u.email, u.role) for u in users],
            'customer_points': customer.points,
        })


try:
    asyncio.run(verify())
finally:
    DB_PATH.unlink(missing_ok=True)
