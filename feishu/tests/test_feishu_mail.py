import csv
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from feishu_mail import (  # noqa: E402
    CSV_NAME,
    FeishuMailAPI,
    InvoiceArchiver,
    download_mail,
    extract_invoice_links,
    invoice_attachments,
    is_invoice_message,
    safe_filename,
)


CN_TZ = timezone(timedelta(hours=8))


def make_message(message_id, subject="电子发票", attachments=None):
    timestamp = int(datetime(2026, 7, 13, 10, 30, tzinfo=CN_TZ).timestamp() * 1000)
    return {
        "message_id": message_id,
        "internal_date": timestamp,
        "subject": subject,
        "body_preview": "",
        "body_plain_text": "",
        "head_from": {"name": "测试商户", "mail_address": "billing@example.com"},
        "attachments": attachments or [],
    }


class FakeAPI:
    def __init__(self, messages, files=None, failures=None, get_failures=None, link_failure=False):
        self.messages = {message["message_id"]: message for message in messages}
        self.files = files or {}
        self.failures = set(failures or [])
        self.get_failures = set(get_failures or [])
        self.link_failure = link_failure

    def list_message_ids(self, limit):
        return list(self.messages)[:limit]

    def get_message(self, message_id):
        if message_id in self.get_failures:
            raise RuntimeError("模拟读取邮件失败")
        return dict(self.messages[message_id])

    def get_attachment_urls(self, message_id, attachment_ids):
        return {attachment_id: f"fake://{attachment_id}" for attachment_id in attachment_ids}

    def download(self, url, destination):
        attachment_id = url.rsplit("/", 1)[-1]
        if attachment_id in self.failures:
            raise RuntimeError("模拟下载失败")
        Path(destination).write_bytes(self.files[attachment_id])

    def download_trusted_invoice_link(self, _url, destination, expected_extension):
        if self.link_failure:
            Path(destination).write_bytes(b"partial")
            raise RuntimeError("模拟外链下载失败")
        content = {".pdf": b"%PDF-1.7 invoice"}[expected_extension]
        Path(destination).write_bytes(content)
        return f"阿里云电子发票{expected_extension}"


class FeishuMailHelpersTest(unittest.TestCase):
    def test_keyword_and_attachment_filter(self):
        message = make_message("m1", subject="Your INVOICE is ready", attachments=[
            {"id": "a1", "filename": "发票.pdf", "is_inline": False},
            {"id": "a2", "filename": "logo.png", "is_inline": True},
            {"id": "a3", "filename": "说明.txt", "is_inline": False},
            {"id": "a4", "filename": "发票.xml", "is_inline": False},
            {"id": "a5", "filename": "发票.ofd", "is_inline": False},
        ])
        self.assertTrue(is_invoice_message(message))
        self.assertEqual(["a1"], [item["id"] for item in invoice_attachments(message)])

    def test_base64url_body_matches_keyword(self):
        message = make_message("m1", subject="普通通知", attachments=[])
        message["body_preview"] = "5oql6ZSA5Ye65beu"
        self.assertTrue(is_invoice_message(message))

    def test_attachment_url_requests_are_batched(self):
        api = FeishuMailAPI("https://example.com", lambda: {})
        batches = []

        def fake_get(_path, params):
            ids = [value for _, value in params]
            batches.append(ids)
            return {"download_urls": [
                {"attachment_id": item, "download_url": f"https://download/{item}"}
                for item in ids
            ]}

        api._get = fake_get
        with mock.patch("feishu_mail.time.sleep") as sleep:
            urls = api.get_attachment_urls("m1", [f"a{index}" for index in range(21)])
        self.assertEqual([20, 1], [len(batch) for batch in batches])
        self.assertTrue(sleep.called)
        self.assertEqual("https://download/a20", urls["a20"])

    def test_explicit_mailbox_is_used_in_api_path(self):
        calls = []

        class Response:
            def json(self):
                return {"code": 0, "data": {"items": [], "has_more": False}}

        class Session:
            def get(self, url, **_kwargs):
                calls.append(url)
                return Response()

        api = FeishuMailAPI(
            "https://example.com", lambda: {}, session=Session(),
            mailbox_id="pay@infidive.com",
        )
        api.list_message_ids(1)
        self.assertEqual(
            ["https://example.com/mail/v1/user_mailboxes/pay@infidive.com/messages"],
            calls,
        )

    def test_api_retries_frequency_limit(self):
        responses = [
            {"code": 99991400, "msg": "request trigger frequency limit"},
            {"code": 0, "data": {"items": [], "has_more": False}},
        ]

        class Response:
            def json(self):
                return responses.pop(0)

        class Session:
            def get(self, _url, **_kwargs):
                return Response()

        api = FeishuMailAPI("https://example.com", lambda: {}, session=Session())
        with mock.patch("feishu_mail.time.sleep") as sleep:
            self.assertEqual([], api.list_message_ids(1))
        sleep.assert_called_once_with(1)

    def test_batch_move_only_changes_folder_and_is_batched(self):
        bodies = []

        class Response:
            def json(self):
                return {"code": 0, "data": {}}

        class Session:
            def post(self, _url, **kwargs):
                bodies.append(kwargs["json"])
                return Response()

        api = FeishuMailAPI("https://example.com", lambda: {}, session=Session())
        api.batch_move([f"m{index}" for index in range(51)], "folder-1")
        self.assertEqual([50, 1], [len(body["message_ids"]) for body in bodies])
        self.assertTrue(all(body["add_folder"] == "folder-1" for body in bodies))
        self.assertTrue(all(set(body) == {"message_ids", "add_folder"} for body in bodies))

    def test_safe_filename_blocks_path_traversal(self):
        self.assertEqual("发票.pdf", safe_filename("../../发票.pdf"))
        self.assertEqual("发票_7月.pdf", safe_filename("发票:7月.pdf"))

    def test_extracts_only_trusted_aliyun_invoice_buttons(self):
        html = """
        <a href="https://t.aliyun.com/pdf">下载PDF发票</a>
        <a href="https://www.aliyun.com/xml">下载XML发票</a>
        <a href="https://oss-cn.aliyuncs.com/ofd">下载OFD发票</a>
        <a href="https://evil.example.com/file">下载PDF发票</a>
        """
        import base64
        message = make_message("m1")
        message["head_from"] = {"mail_address": "system@notice.aliyun.com"}
        message["body_html"] = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
        links = extract_invoice_links(message)
        self.assertEqual([".pdf"], [item["expected_extension"] for item in links])
        self.assertTrue(all(item["source_type"] == "body_link" for item in links))

    def test_trusted_link_validates_redirect_and_content(self):
        class Response:
            def __init__(self, status, headers, content=b""):
                self.status_code = status
                self.headers = headers
                self.content = content

            def iter_content(self, _size):
                yield self.content

        class Session:
            def __init__(self):
                self.responses = [
                    Response(302, {"Location": "https://files.aliyuncs.com/invoice.pdf"}),
                    Response(200, {
                        "Content-Type": "application/pdf",
                        "Content-Disposition": 'attachment; filename="original.pdf"',
                    }, b"%PDF-1.7 invoice"),
                ]

            def get(self, _url, **_kwargs):
                return self.responses.pop(0)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file.part"
            api = FeishuMailAPI("https://example.com", lambda: {}, session=Session())
            name = api.download_trusted_invoice_link(
                "https://t.aliyun.com/download", path, ".pdf",
            )
            self.assertEqual("original.pdf", name)
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_trusted_link_rejects_html_and_untrusted_host(self):
        class Response:
            status_code = 200
            headers = {"Content-Type": "text/html"}

            def iter_content(self, _size):
                yield b"<html>login</html>"

        class Session:
            def get(self, _url, **_kwargs):
                return Response()

        api = FeishuMailAPI("https://example.com", lambda: {}, session=Session())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "file.part"
            with self.assertRaisesRegex(RuntimeError, "网页"):
                api.download_trusted_invoice_link("https://t.aliyun.com/file", path, ".pdf")
            with self.assertRaisesRegex(RuntimeError, "非阿里云"):
                api.download_trusted_invoice_link("https://evil.example.com/file", path, ".pdf")


class InvoiceArchiverTest(unittest.TestCase):
    def test_body_links_are_archived_and_idempotent(self):
        import base64
        html = """
        <a href="https://t.aliyun.com/pdf">下载PDF发票</a>
        <a href="https://t.aliyun.com/xml">下载XML发票</a>
        <a href="https://t.aliyun.com/ofd">下载OFD发票</a>
        """
        message = make_message("m1")
        message["head_from"] = {"mail_address": "system@notice.aliyun.com"}
        message["body_html"] = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
        api = FakeAPI([message])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            first = InvoiceArchiver(api, root).collect()
            second = InvoiceArchiver(api, root).collect()
            self.assertEqual(1, first["candidate_body_links"])
            self.assertEqual(1, first["saved"])
            self.assertEqual(1, second["skipped_known"])
            self.assertEqual(1, len(list((root / "2026" / "07").iterdir())))

    def test_body_link_failure_leaves_no_partial_or_csv(self):
        import base64
        message = make_message("m1")
        message["head_from"] = {"mail_address": "system@notice.aliyun.com"}
        html = '<a href="https://t.aliyun.com/pdf">下载PDF发票</a>'
        message["body_html"] = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
        api = FakeAPI([message], link_failure=True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            result = InvoiceArchiver(api, root).collect()
            self.assertEqual(1, result["failed"])
            self.assertEqual([], list(root.rglob("*.part")))
            self.assertFalse((root / CSV_NAME).exists())

    def test_collect_then_rerun_is_idempotent(self):
        message = make_message("m1", attachments=[
            {"id": "a1", "filename": "深圳发票.pdf", "is_inline": False},
            {"id": "a2", "filename": "签名.png", "is_inline": True},
        ])
        api = FakeAPI([message], {"a1": b"invoice-one"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            first = InvoiceArchiver(api, root).collect()
            second = InvoiceArchiver(api, root).collect()

            self.assertEqual(1, first["saved"])
            self.assertEqual(0, second["saved"])
            self.assertEqual(1, second["skipped_known"])
            saved = root / "2026" / "07" / "深圳发票.pdf"
            self.assertEqual(b"invoice-one", saved.read_bytes())
            with open(root / CSV_NAME, newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(1, len(rows))
            self.assertEqual("已保存", rows[0]["处理状态"])
            self.assertEqual("me", rows[0]["邮箱"])

    def test_same_hash_is_recorded_without_duplicate_file(self):
        messages = [
            make_message("m1", attachments=[{"id": "a1", "filename": "甲.pdf", "is_inline": False}]),
            make_message("m2", attachments=[{"id": "a2", "filename": "乙.pdf", "is_inline": False}]),
        ]
        api = FakeAPI(messages, {"a1": b"same", "a2": b"same"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            result = InvoiceArchiver(api, root).collect()
            files = [path for path in root.rglob("*") if path.is_file() and path.name != CSV_NAME]
            with open(root / CSV_NAME, newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))

            self.assertEqual(1, result["saved"])
            self.assertEqual(1, result["duplicates"])
            self.assertEqual(1, len(files))
            self.assertEqual(2, len(rows))
            self.assertEqual("重复文件", rows[1]["处理状态"])
            self.assertEqual(rows[0]["保存文件"], rows[1]["保存文件"])

    def test_same_name_with_different_content_gets_suffix(self):
        messages = [
            make_message("m1", attachments=[{"id": "a1", "filename": "发票.pdf", "is_inline": False}]),
            make_message("m2", attachments=[{"id": "a2", "filename": "发票.pdf", "is_inline": False}]),
        ]
        api = FakeAPI(messages, {"a1": b"one", "a2": b"two"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            InvoiceArchiver(api, root).collect()
            month = root / "2026" / "07"
            self.assertEqual(b"one", (month / "发票.pdf").read_bytes())
            self.assertEqual(b"two", (month / "发票_2.pdf").read_bytes())

    def test_success_is_recorded_when_later_mail_fails(self):
        messages = [
            make_message("m1", attachments=[{"id": "a1", "filename": "发票.pdf", "is_inline": False}]),
            make_message("m2", attachments=[{"id": "a2", "filename": "发票.pdf", "is_inline": False}]),
        ]
        api = FakeAPI(messages, {"a1": b"one"}, get_failures={"m2"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            result = InvoiceArchiver(api, root).collect()
            with open(root / CSV_NAME, newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))

            self.assertEqual(1, result["saved"])
            self.assertEqual(1, result["failed"])
            self.assertEqual(1, len(rows))

    def test_mail_download_failure_leaves_no_partial_file(self):
        message = make_message("m1", attachments=[
            {"id": "a1", "filename": "失败发票.pdf", "is_inline": False},
        ])
        api = FakeAPI([message], {"a1": b"unused"}, failures={"a1"})
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "下载"
            with self.assertRaisesRegex(RuntimeError, "模拟下载失败"):
                download_mail(api, "m1", target)
            self.assertFalse((target / "失败发票.pdf").exists())
            self.assertEqual([], list(target.rglob("*.part")))

    def test_download_failure_leaves_no_partial_or_csv(self):
        message = make_message("m1", attachments=[
            {"id": "a1", "filename": "失败发票.pdf", "is_inline": False},
        ])
        api = FakeAPI([message], {"a1": b"unused"}, failures={"a1"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            result = InvoiceArchiver(api, root).collect()
            self.assertEqual(1, result["failed"])
            self.assertFalse((root / CSV_NAME).exists())
            self.assertEqual([], list(root.rglob("*.part")))

    def test_dry_run_does_not_write(self):
        message = make_message("m1", attachments=[
            {"id": "a1", "filename": "预览发票.pdf", "is_inline": False},
        ])
        api = FakeAPI([message], {"a1": b"%PDF-1.7 invoice"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "发票"
            result = InvoiceArchiver(api, root).collect(dry_run=True)
            self.assertEqual(1, result["candidate_attachments"])
            self.assertEqual("预览发票.pdf", result["candidates"][0]["filename"])
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
