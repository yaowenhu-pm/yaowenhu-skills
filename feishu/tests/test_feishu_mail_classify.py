import base64
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from feishu_mail_classify import (  # noqa: E402
    MailClassificationManager,
    classify_message,
    rule_blueprints,
)


def encoded(value):
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def message(message_id, sender, subject, body=""):
    return {
        "message_id": message_id,
        "head_from": {"mail_address": sender},
        "subject": subject,
        "body_preview": "",
        "body_plain_text": encoded(body),
        "body_html": "",
        "attachments": [],
    }


class FakeAPI:
    def __init__(self, messages=None):
        self.messages = {item["message_id"]: item for item in (messages or [])}
        self.folders = []
        self.rules = []
        self.created_folders = []
        self.created_rules = []
        self.moves = []

    def list_message_ids(self, limit):
        return list(self.messages)[:limit]

    def get_message(self, message_id):
        return dict(self.messages[message_id])

    def list_folders(self):
        return list(self.folders)

    def create_folder(self, name, parent_folder_id="0"):
        folder = {
            "id": str(len(self.folders) + 1),
            "name": name,
            "parent_folder_id": str(parent_folder_id),
        }
        self.folders.append(folder)
        self.created_folders.append(name)
        return folder

    def list_rules(self):
        return list(self.rules)

    def create_rule(self, rule):
        self.rules.append(rule)
        self.created_rules.append(rule["name"])
        return rule

    def batch_move(self, message_ids, folder_id):
        self.moves.append((list(message_ids), str(folder_id)))


class ClassificationRulesTest(unittest.TestCase):
    def test_conservative_priority(self):
        cases = [
            (message("m1", "system@notice.aliyun.com", "电子发票已开具"), "财务发票"),
            (message("m2", "news@tm.openai.com", "产品更新", "unsubscribe"), "AI产品"),
            (message("m3", "noreply@github.com", "Review requested on pull request"), "开发通知"),
            (message("m4", "noreply@github.com", "Security vulnerability alert"), None),
            (message("m5", "person@infidive.com", "工作安排"), None),
            (message("m6", "unknown@example.com", "普通通知"), None),
        ]
        for item, expected in cases:
            with self.subTest(message_id=item["message_id"]):
                self.assertEqual(expected, classify_message(item))

    def test_native_rules_are_move_only(self):
        blueprints = list(rule_blueprints())
        self.assertTrue(blueprints)
        self.assertTrue(all(item["target"] in {"财务发票", "AI产品", "开发通知"} for item in blueprints))
        self.assertTrue(all(item["conditions"] for item in blueprints))


class ClassificationManagerTest(unittest.TestCase):
    def test_install_preview_has_no_writes(self):
        api = FakeAPI()
        result = MailClassificationManager(api).install(apply=False)
        self.assertIn("自动分类", result["missing_folders"])
        self.assertTrue(result["missing_rules"])
        self.assertEqual([], api.created_folders)
        self.assertEqual([], api.created_rules)

    def test_install_apply_is_idempotent(self):
        api = FakeAPI()
        first = MailClassificationManager(api).install(apply=True)
        second = MailClassificationManager(api).install(apply=True)
        self.assertEqual(4, len(first["created_folders"]))
        self.assertEqual(len(list(rule_blueprints())), len(first["created_rules"]))
        self.assertEqual([], second["created_folders"])
        self.assertEqual([], second["created_rules"])

    def test_classify_preview_does_not_move(self):
        api = FakeAPI([
            message("m1", "system@notice.aliyun.com", "电子发票已开具"),
            message("m2", "person@infidive.com", "工作邮件"),
        ])
        result = MailClassificationManager(api).classify(limit=100, apply=False)
        self.assertEqual(1, result["classified"])
        self.assertEqual(1, result["kept_in_inbox"])
        self.assertEqual([], api.moves)

    def test_classify_apply_moves_only_matches(self):
        api = FakeAPI([
            message("m1", "system@notice.aliyun.com", "电子发票已开具"),
            message("m2", "unknown@example.com", "普通邮件"),
        ])
        MailClassificationManager(api).install(apply=True)
        result = MailClassificationManager(api).classify(limit=100, apply=True)
        self.assertEqual(1, result["moved"])
        self.assertEqual(["m1"], api.moves[0][0])


if __name__ == "__main__":
    unittest.main()
