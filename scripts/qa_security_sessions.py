"""Cookie session, CSRF, revocation and security-header QA for Loyalyn v4.1.

Runs against an isolated SQLite database and never touches production data.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

DB = Path('/tmp/loyalyn-v41-security.db')
DB.unlink(missing_ok=True)
os.environ.update({
    'DATABASE_URL': f'sqlite+aiosqlite:///{DB}',
    'BOOTSTRAP_ADMIN_EMAIL': 'owner@example.com',
    'BOOTSTRAP_ADMIN_PASSWORD': 'OwnerPass123!',
    'JWT_SECRET': 's' * 64,
    'ENCRYPTION_KEY': 'e' * 64,
    'ENVIRONMENT': 'production',
    'COOKIE_DOMAIN': '.loyalyn.site',
    'CORS_ORIGINS': 'https://app.loyalyn.site',
    'PUBLIC_API_URL': 'https://api.loyalyn.site',
    'PUBLIC_WEB_URL': 'https://app.loyalyn.site',
    'WALLET_STORAGE_DIR': '/tmp/loyalyn-v41-security-wallet',
})

import httpx
from app.db.session import engine
from app.main import app
from app.models import Base


def assert_status(response: httpx.Response, expected: int) -> None:
    if response.status_code != expected:
        raise AssertionError(f'{response.request.method} {response.request.url}: expected {expected}, got {response.status_code}: {response.text}')


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url='https://api.loyalyn.site') as client:
            login = await client.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'OwnerPass123!'}, headers={'Origin': 'https://app.loyalyn.site'})
            assert_status(login, 200)
            set_cookie = '\n'.join(login.headers.get_list('set-cookie')).lower()
            assert 'loyalyn_access=' in set_cookie and 'httponly' in set_cookie and 'secure' in set_cookie
            assert 'loyalyn_refresh=' in set_cookie and 'path=/api/auth' in set_cookie
            assert 'loyalyn_csrf=' in set_cookie and ('domain=loyalyn.site' in set_cookie or 'domain=.loyalyn.site' in set_cookie)
            access = client.cookies.get('loyalyn_access', domain='api.loyalyn.site')
            refresh = client.cookies.get('loyalyn_refresh', domain='api.loyalyn.site')
            csrf = client.cookies.get('loyalyn_csrf', domain='.loyalyn.site') or client.cookies.get('loyalyn_csrf', domain='loyalyn.site')
            assert access and refresh and csrf

            me = await client.get('/api/auth/me')
            assert_status(me, 200)
            assert me.json()['role'] == 'platform_owner'

            blocked = await client.post('/api/auth/logout', headers={'Origin': 'https://app.loyalyn.site'})
            assert_status(blocked, 403)

            old_refresh = refresh
            rotated = await client.post('/api/auth/refresh', headers={'Origin': 'https://app.loyalyn.site', 'X-Loyalyn-CSRF': csrf})
            assert_status(rotated, 200)
            next_refresh = client.cookies.get('loyalyn_refresh', domain='api.loyalyn.site')
            next_access = client.cookies.get('loyalyn_access', domain='api.loyalyn.site')
            next_csrf = client.cookies.get('loyalyn_csrf', domain='.loyalyn.site') or client.cookies.get('loyalyn_csrf', domain='loyalyn.site')
            assert next_refresh and next_refresh != old_refresh and next_access and next_access != access and next_csrf

            async with httpx.AsyncClient(transport=transport, base_url='https://api.loyalyn.site') as replay:
                replay.cookies.set('loyalyn_refresh', old_refresh, domain='api.loyalyn.site', path='/api/auth')
                replay.cookies.set('loyalyn_csrf', csrf, domain='.loyalyn.site', path='/')
                replay_result = await replay.post('/api/auth/refresh', headers={'Origin': 'https://app.loyalyn.site', 'X-Loyalyn-CSRF': csrf})
                assert_status(replay_result, 401)

            logout = await client.post('/api/auth/logout', headers={'Origin': 'https://app.loyalyn.site', 'X-Loyalyn-CSRF': next_csrf})
            assert_status(logout, 200)

            # The access token captured before logout is unusable because its server session was revoked.
            async with httpx.AsyncClient(transport=transport, base_url='https://api.loyalyn.site') as revoked:
                revoked.cookies.set('loyalyn_access', next_access, domain='api.loyalyn.site', path='/')
                denied = await revoked.get('/api/auth/me')
                assert_status(denied, 401)

            health = await client.get('/api/health')
            assert_status(health, 200)
            headers = {k.lower(): v for k, v in health.headers.items()}
            assert headers['strict-transport-security'].startswith('max-age=')
            assert headers['x-frame-options'] == 'DENY'
            assert headers['x-content-type-options'] == 'nosniff'
            assert headers['referrer-policy'] == 'strict-origin-when-cross-origin'
            assert 'camera=(self)' in headers['permissions-policy']

            print(json.dumps({
                'ok': True,
                'version': '4.1.0',
                'http_only_access': True,
                'rotating_refresh': True,
                'csrf': True,
                'logout_revokes_access': True,
                'security_headers': True,
            }, ensure_ascii=False))

    DB.unlink(missing_ok=True)


if __name__ == '__main__':
    asyncio.run(main())
