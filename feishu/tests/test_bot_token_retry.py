import importlib.util
import os
from pathlib import Path
import subprocess
import unittest


def _load_feishu():
    script = Path(__file__).resolve().parents[1] / "scripts" / "feishu.py"
    original_exists = os.path.exists
    original_run = subprocess.run
    original_check_output = subprocess.check_output
    os.path.exists = lambda path: True if str(path).endswith(".update-check") else original_exists(path)
    subprocess.run = lambda *args, **kwargs: None
    subprocess.check_output = lambda *args, **kwargs: b""
    try:
        spec = importlib.util.spec_from_file_location("feishu_bot_retry_test", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.path.exists = original_exists
        subprocess.run = original_run
        subprocess.check_output = original_check_output


feishu = _load_feishu()


class _Response:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def json(self):
        return self.body


class BotTokenRetryTest(unittest.TestCase):
    def setUp(self):
        self.original_app = feishu._app
        self.original_post = feishu.requests.post
        self.original_patch = feishu.requests.patch
        self.original_cache = dict(feishu._BOT_TOKEN_CACHE)
        feishu._app = lambda: ("app-id", "app-secret")
        feishu._invalidate_bot_token()

    def tearDown(self):
        feishu._app = self.original_app
        feishu.requests.post = self.original_post
        feishu.requests.patch = self.original_patch
        feishu._BOT_TOKEN_CACHE.update(self.original_cache)

    def test_code_99991663_forces_one_refresh_and_retries_message(self):
        token_calls = []
        message_headers = []

        def post(url, **kwargs):
            if url.endswith("/auth/v3/tenant_access_token/internal"):
                token_calls.append(url)
                return _Response({"tenant_access_token": f"token-{len(token_calls)}", "expire": 7200})
            message_headers.append(kwargs["headers"]["Authorization"])
            if len(message_headers) == 1:
                return _Response({"code": 99991663, "msg": "tenant access token invalid"})
            return _Response({"code": 0, "data": {"message_id": "om_1"}})

        feishu.requests.post = post
        self.assertEqual(feishu.send_text_bot("oc_1", "chat_id", "hi"), "✓ message_id=om_1")
        self.assertEqual(len(token_calls), 2)
        self.assertEqual(message_headers, ["Bearer token-1", "Bearer token-2"])

    def test_http_401_forces_one_refresh_and_retries_cardkit(self):
        token_calls = []
        card_headers = []

        def post(url, **kwargs):
            self.assertTrue(url.endswith("/auth/v3/tenant_access_token/internal"))
            token_calls.append(url)
            return _Response({"tenant_access_token": f"token-{len(token_calls)}", "expire": 7200})

        def patch(url, **kwargs):
            card_headers.append(kwargs["headers"]["Authorization"])
            if len(card_headers) == 1:
                return _Response({"code": 0}, status_code=401)
            return _Response({"code": 0})

        feishu.requests.post = post
        feishu.requests.patch = patch
        self.assertEqual(feishu.update_card_bot("om_1", {"elements": []}), "✓ updated")
        self.assertEqual(len(token_calls), 2)
        self.assertEqual(card_headers, ["Bearer token-1", "Bearer token-2"])

    def test_second_invalid_response_is_not_retried_again(self):
        token_calls = []
        message_calls = []

        def post(url, **kwargs):
            if url.endswith("/auth/v3/tenant_access_token/internal"):
                token_calls.append(url)
                return _Response({"tenant_access_token": f"token-{len(token_calls)}", "expire": 7200})
            message_calls.append(url)
            return _Response({"code": 99991663, "msg": "tenant access token invalid"})

        feishu.requests.post = post
        with self.assertRaises(SystemExit):
            feishu.send_text_bot("oc_1", "chat_id", "hi")
        self.assertEqual(len(token_calls), 2)
        self.assertEqual(len(message_calls), 2)


if __name__ == "__main__":
    unittest.main()
