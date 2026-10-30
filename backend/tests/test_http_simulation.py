"""Exercise ASGI requests without sockets, external services or extra packages."""
import asyncio
import json
import threading
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from app.routers.simulation import router
from app.models.results import SimulationResult

app = FastAPI()
app.include_router(router)
TEXT = '* divider\nV1 in 0 5\nR1 in out 1k\nR2 out 0 1k\n.op\n.end'


async def request(path, payload=None, method='POST'):
    messages = []
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return dict(type='http.request', body=json.dumps(payload).encode(), more_body=False)
        await asyncio.Future()
    async def send(message):
        messages.append(message)
    scope = dict(type='http', asgi={'version':'3.0'}, http_version='1.1', method=method,
                 scheme='http', path=path, raw_path=path.encode(), query_string=b'',
                 headers=[(b'content-type',b'application/json')], server=('test',80), client=('test',1), root_path='')
    await app(scope, receive, send)
    status = next(m['status'] for m in messages if m['type']=='http.response.start')
    body = b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
    return status, json.loads(body)


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_json_equivalence_and_export(self):
        status, parsed = await request('/spice/parse', {'text':TEXT})
        self.assertEqual(status, 200)
        status, result = await request('/simulate', parsed['request'])
        self.assertEqual(status, 200)
        status, text_result = await request('/simulate/spice', {'text':TEXT})
        self.assertEqual(status, 200)
        self.assertEqual(result, text_result)
        self.assertAlmostEqual(result['node_voltages']['OUT'][0], 2.5)
        status, exported = await request('/spice/export', {'request':parsed['request']})
        self.assertEqual(status, 200)
        status, again = await request('/simulate/spice', exported)
        self.assertEqual(again, result)

    async def test_validation_and_solver_errors(self):
        status, error = await request('/spice/parse', {'text':'.include vendor.lib'})
        self.assertEqual(status, 400)
        self.assertIn('第 1 行', error['detail'])
        status, _ = await request('/simulate', {'settings':{'mode':'dc'}})
        self.assertEqual(status, 422)
        status, _ = await request('/simulate/spice', {'text':'* floating\nR1 a b 1k\nR2 c 0 1k'})
        self.assertEqual(status, 400)

    async def test_json_solve_does_not_block_health(self):
        started, finished, release = threading.Event(), threading.Event(), threading.Event()
        def blocking_solve(_):
            started.set()
            release.wait(1)
            finished.set()
            return SimulationResult(mode='dc', x_values=[0], node_voltages={}, branch_currents={})
        with patch('app.routers.simulation.run_simulation', side_effect=blocking_solve):
            task = asyncio.create_task(request('/simulate', {'elements':[], 'settings':{'mode':'dc'}}))
            try:
                while not started.is_set():
                    await asyncio.sleep(.005)
                status, result = await request('/health', method='GET')
                self.assertEqual(status, 200)
                self.assertEqual(result, {'status':'ok'})
                self.assertFalse(finished.is_set(), 'JSON solver blocked the event loop')
            finally:
                release.set()
                await task

if __name__ == '__main__':
    unittest.main()
