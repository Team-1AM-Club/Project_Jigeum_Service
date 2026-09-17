"""Real MCP stdio -> loopback FastAPI -> disposable SQLite verification.

Uses mock providers, no Hermes/model request and no production database.
Run with the Python environment containing backend + MCP requirements.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

import httpx
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent

ROOT = Path(__file__).resolve().parents[1]


async def check(base_url):
    parameters = StdioServerParameters(command=sys.executable,
        args=[str(ROOT / 'mcp-server/jigeum_mcp_server.py')],
        env={**os.environ, 'JIGEUM_MODE': 'http', 'JIGEUM_API_BASE_URL': base_url})
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {'get_capabilities', 'search_places', 'interpret_trip',
                             'confirm_trip', 'plan_journey', 'replan_journey'}, names

            async def call(name, arguments):
                result = await session.call_tool(name, arguments)
                assert not result.is_error, result
                return json.loads(next(item.text for item in result.content if isinstance(item, TextContent)))

            assert (await call('get_capabilities', {}))['meta']['is_demo'] is True
            places = await call('search_places', {'query': '서울역'})
            assert places['data']['places'][0]['place_id'] == 'place_seoul_station', places
            trip = dict(kind='appointment', origin_place_id='place_seoul_station',
                        destination_place_id='place_gangnam_station',
                        arrival_deadline='2026-09-17T19:00:00+09:00',
                        arrival_preference_minutes=10, transport_modes=['subway', 'bus'], service_date=None)
            interpreted = await call('interpret_trip', {'text': '서울역에서 강남역', 'context': trip})
            assert interpreted['status'] == 'needs_confirmation', interpreted
            meta = interpreted['meta']
            state = dict(conversation_id=meta['conversation_id'], expected_revision=meta['revision'])
            denied = await call('plan_journey', dict(state, trip=trip))
            assert denied['error']['code'] == 'USER_CONFIRMATION_REQUIRED', denied
            denied = await call('confirm_trip', dict(state, confirmed_data=trip, user_confirmed=False))
            assert denied['error']['code'] == 'USER_CONFIRMATION_REQUIRED', denied
            confirmed = await call('confirm_trip', dict(state, confirmed_data=trip, user_confirmed=True))
            assert confirmed['status'] == 'ok', confirmed
            stale = await call('plan_journey', dict(state, trip=trip))
            assert stale['error']['code'] == 'CONVERSATION_VERSION_CONFLICT', stale
            state['expected_revision'] = confirmed['meta']['revision']
            planned = await call('plan_journey', dict(state, trip=trip))
            assert planned['status'] == 'ok', planned
            plan = planned['data']
            option = plan['comparison']['options'][0]
            # Simulate the test user's explicit selection; the adapter never selects it.
            previous = dict(plan_id=plan['plan_id'], selected_option_id=option['option_id'],
                            recommended_leave_at=option['recommended_leave_at'],
                            estimated_arrival_at=option['target_arrival_at'])
            state['expected_revision'] = planned['meta']['revision']
            replanned = await call('replan_journey', dict(state, trip=trip, previous_plan=previous,
                current_origin_place_id=trip['origin_place_id'], reason='manual', user_confirmed=True))
            assert replanned['status'] == 'ok', replanned
            assert replanned['data']['comparison']['previous_plan_preserved'] is True
            assert replanned['meta']['revision'] == state['expected_revision'] + 1

            last_trip = dict(trip, kind='last_journey', arrival_deadline=None,
                             arrival_preference_minutes=0, service_date='2026-09-17')
            last = await call('interpret_trip', {'text': '서울역에서 강남역 막차', 'context': last_trip})
            state = dict(conversation_id=last['meta']['conversation_id'], expected_revision=last['meta']['revision'])
            last = await call('confirm_trip', dict(state, confirmed_data=last_trip, user_confirmed=True))
            assert last['status'] == 'ok', last
            state['expected_revision'] = last['meta']['revision']
            last = await call('plan_journey', dict(state, trip=last_trip))
            assert last['status'] == 'ok' and last['data']['is_last_journey'] is True, last
            print('PASS: MCP initialize + 6 tools; places -> interpret -> reject unconfirmed -> confirm '
                  '-> stale revision rejected -> plan -> replan preserves prior plan; last journey. Mock data.')


def main():
    sys.path.insert(0, str(ROOT / 'backend'))
    with tempfile.TemporaryDirectory(prefix='jigeum-mcp-http-') as temporary:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(temporary) / 'smoke.db').as_posix()
        from app.main import app
        from app.db import engine
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/api/v1/health').status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError('Backend startup timed out')
            asyncio.run(check(f'http://127.0.0.1:{port}/api/v1'))
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            engine.dispose()
            assert not thread.is_alive(), 'Backend did not stop'


if __name__ == '__main__':
    main()
