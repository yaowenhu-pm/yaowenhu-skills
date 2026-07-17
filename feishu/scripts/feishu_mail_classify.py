#!/usr/bin/env python3
"""飞书个人邮箱的保守分类规则与历史邮件预览。"""

import argparse
from collections import defaultdict

from feishu_mail import decode_mail_text, sender_text


ROOT_FOLDER = "自动分类"
TARGET_FOLDERS = ("财务发票", "AI产品", "开发通知")
INVOICE_SENDERS = {"system@notice.aliyun.com"}
AI_DOMAINS = ("tm.openai.com", "email.openai.com", "mail.anthropic.com")
AI_NEWSLETTER_MARKERS = ("unsubscribe", "退订", "取消订阅")
GITHUB_SENDER = "noreply@github.com"
GITHUB_ROUTINE_MARKERS = (
    "pull request", "issue", "commented", "mentioned", "invited you", "review requested",
)
SECURITY_MARKERS = (
    "登录", "密码", "验证码", "验证", "安全", "风险", "漏洞",
    "login", "password", "verify", "verification", "security", "alert",
    "vulnerability", "dependabot", "account",
)
INVOICE_MARKERS = ("发票", "账单", "报销", "invoice", "receipt")
WORK_DOMAIN = "infidive.com"
RULE_PREFIX = "[Codex]"


def _address(message):
    return str((message.get("head_from") or {}).get("mail_address", "")).casefold()


def _mail_text(message):
    return " ".join((
        str(message.get("subject", "")),
        decode_mail_text(message.get("body_preview")),
        decode_mail_text(message.get("body_plain_text")),
        decode_mail_text(message.get("body_html")),
    )).casefold()


def _domain_matches(address, domain):
    return address.endswith("@" + domain) or address == domain


def classify_message(message):
    address = _address(message)
    text = _mail_text(message)
    subject = str(message.get("subject", "")).casefold()
    if any(marker in subject for marker in SECURITY_MARKERS):
        return None
    if _domain_matches(address, WORK_DOMAIN):
        return None
    if address in INVOICE_SENDERS and any(marker in text for marker in INVOICE_MARKERS):
        return "财务发票"
    if any(_domain_matches(address, domain) for domain in AI_DOMAINS):
        if any(marker in text for marker in AI_NEWSLETTER_MARKERS):
            return "AI产品"
    if address == GITHUB_SENDER:
        if any(marker in subject for marker in GITHUB_ROUTINE_MARKERS):
            return "开发通知"
    return None


def _condition(condition_type, operator, value):
    return {"type": condition_type, "operator": operator, "input": value}


def rule_blueprints():
    security_exclusions = [_condition(6, 2, marker) for marker in SECURITY_MARKERS]
    yield {
        "name": f"{RULE_PREFIX} 阿里云电子发票", "target": "财务发票",
        "conditions": [
            _condition(1, 5, "system@notice.aliyun.com"),
            _condition(6, 1, "发票"),
        ],
    }
    for domain in AI_DOMAINS:
        for marker in AI_NEWSLETTER_MARKERS:
            yield {
                "name": f"{RULE_PREFIX} AI产品-{domain}-{marker}", "target": "AI产品",
                "conditions": [
                    _condition(1, 4, domain),
                    _condition(7, 1, marker),
                    *security_exclusions,
                ],
            }
    for marker in GITHUB_ROUTINE_MARKERS:
        yield {
            "name": f"{RULE_PREFIX} 开发通知-{marker}", "target": "开发通知",
            "conditions": [
                _condition(1, 5, GITHUB_SENDER),
                _condition(6, 1, marker),
                *security_exclusions,
            ],
        }


def _rule_payload(blueprint, folder_id):
    return {
        "condition": {"match_type": 1, "items": blueprint["conditions"]},
        "action": {"items": [{"type": 11, "input": str(folder_id)}]},
        "ignore_the_rest_of_rules": True,
        "name": blueprint["name"],
        "is_enable": True,
    }


def _find_folder(folders, name, parent_id):
    for folder in folders:
        if folder.get("name") == name and str(folder.get("parent_folder_id")) == str(parent_id):
            return folder
    return None


class MailClassificationManager:
    def __init__(self, api):
        self.api = api

    def install(self, apply=False):
        folders = list(self.api.list_folders())
        rules = list(self.api.list_rules())
        existing_rule_names = {rule.get("name") for rule in rules}
        blueprints = list(rule_blueprints())
        root = _find_folder(folders, ROOT_FOLDER, "0")
        missing_folders = []
        if not root:
            missing_folders.append(ROOT_FOLDER)
        for name in TARGET_FOLDERS:
            if not root or not _find_folder(folders, name, root.get("id")):
                missing_folders.append(f"{ROOT_FOLDER}/{name}")
        missing_rules = [
            item["name"] for item in blueprints if item["name"] not in existing_rule_names
        ]
        result = {
            "apply": apply,
            "missing_folders": missing_folders,
            "missing_rules": missing_rules,
            "created_folders": [],
            "created_rules": [],
        }
        if not apply:
            return result

        if not root:
            root = self.api.create_folder(ROOT_FOLDER, "0")
            folders.append(root)
            result["created_folders"].append(ROOT_FOLDER)
        folder_ids = {}
        for name in TARGET_FOLDERS:
            folder = _find_folder(folders, name, root["id"])
            if not folder:
                folder = self.api.create_folder(name, root["id"])
                folders.append(folder)
                result["created_folders"].append(f"{ROOT_FOLDER}/{name}")
            folder_ids[name] = folder["id"]

        for blueprint in blueprints:
            if blueprint["name"] in existing_rule_names:
                continue
            self.api.create_rule(_rule_payload(blueprint, folder_ids[blueprint["target"]]))
            result["created_rules"].append(blueprint["name"])
        return result

    def classify(self, limit=100, apply=False):
        folders = list(self.api.list_folders())
        root = _find_folder(folders, ROOT_FOLDER, "0")
        folder_ids = {}
        if root:
            for name in TARGET_FOLDERS:
                folder = _find_folder(folders, name, root.get("id"))
                if folder:
                    folder_ids[name] = folder.get("id")
        if apply and len(folder_ids) != len(TARGET_FOLDERS):
            raise RuntimeError("分类文件夹尚未安装，请先运行 mail-classify-install --apply")

        groups = defaultdict(list)
        candidates = []
        scanned = 0
        for message_id in self.api.list_message_ids(limit):
            scanned += 1
            message = self.api.get_message(message_id)
            target = classify_message(message)
            if not target:
                continue
            groups[target].append(message_id)
            candidates.append({
                "message_id": message_id,
                "sender": sender_text(message),
                "subject": message.get("subject", ""),
                "target": f"{ROOT_FOLDER}/{target}",
            })

        moved = 0
        if apply:
            for target, message_ids in groups.items():
                self.api.batch_move(message_ids, folder_ids[target])
                moved += len(message_ids)
        return {
            "apply": apply,
            "scanned": scanned,
            "classified": len(candidates),
            "kept_in_inbox": scanned - len(candidates),
            "counts": {target: len(ids) for target, ids in groups.items()},
            "moved": moved,
            "candidates": candidates,
        }


def parse_install_args(arguments):
    parser = argparse.ArgumentParser(prog="feishu.py mail-classify-install")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(arguments)


def parse_classify_args(arguments):
    parser = argparse.ArgumentParser(prog="feishu.py mail-classify")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(arguments)
