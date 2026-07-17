#!/usr/bin/env python3
"""飞书个人邮箱 API 与通用附件下载。"""

import argparse
import base64
import csv
import hashlib
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests


CN_TZ = timezone(timedelta(hours=8))
DEFAULT_ROOT = "/Users/admin/Desktop/发票"
KEYWORDS = ("发票", "电子票", "数电票", "行程单", "电子客票", "报销", "invoice", "receipt")
INVOICE_EXTENSIONS = {".pdf"}
CSV_NAME = "发票汇总.csv"
CSV_FIELDS = (
    "邮箱", "邮件日期", "发件人", "主题", "原文件名", "保存文件", "SHA256",
    "message_id", "attachment_id", "来源类型", "来源ID", "处理状态",
)
CSV_ESCAPE_FIELDS = {"发件人", "主题", "原文件名", "保存文件"}
TRUSTED_INVOICE_SENDER = "system@notice.aliyun.com"
TRUSTED_INVOICE_HOST_SUFFIXES = (".aliyun.com", ".aliyuncs.com")
INVOICE_LINK_LABELS = {"PDF": ".pdf"}


class FeishuMailAPI:
    def __init__(self, base_url, headers, session=None, mailbox_id="me"):
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.session = session or requests
        self.mailbox_id = str(mailbox_id).strip() or "me"
        self._next_attachment_url_at = 0.0
        self._next_mail_write_at = 0.0

    def _mailbox_path(self, suffix=""):
        mailbox_id = quote(self.mailbox_id, safe="@.")
        return f"/mail/v1/user_mailboxes/{mailbox_id}{suffix}"

    def _request(self, method, path, params=None, body=None):
        for attempt in range(4):
            response = getattr(self.session, method)(
                f"{self.base_url}{path}", headers=self.headers(), params=params,
                json=body, timeout=30,
            )
            data = response.json()
            if data.get("code") == 99991400 and attempt < 3:
                time.sleep(1)
                continue
            if data.get("code") != 0:
                raise RuntimeError(f"{path}: {data.get('msg')} ({data.get('code')})")
            return data.get("data", {})

    def _get(self, path, params=None):
        return self._request("get", path, params=params)

    def _post(self, path, body):
        return self._request("post", path, body=body)

    def list_message_ids(self, limit=20):
        ids, page_token = [], ""
        limit = max(0, int(limit))
        while len(ids) < limit:
            params = {"folder_id": "INBOX", "page_size": min(20, limit - len(ids))}
            if page_token:
                params["page_token"] = page_token
            data = self._get(self._mailbox_path("/messages"), params)
            ids.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")
            if not page_token:
                break
        return ids[:limit]

    def get_message(self, message_id):
        data = self._get(
            self._mailbox_path(f"/messages/{message_id}"), {"format": "full"},
        )
        message = data.get("message", {})
        message.setdefault("message_id", message_id)
        return message

    def list_folders(self):
        return self._get(
            self._mailbox_path("/folders"), {"folder_type": 2},
        ).get("items", [])

    def create_folder(self, name, parent_folder_id="0"):
        self._pace_mail_write()
        try:
            return self._post(
                self._mailbox_path("/folders"),
                {"name": name, "parent_folder_id": str(parent_folder_id)},
            ).get("folder", {})
        finally:
            self._next_mail_write_at = time.monotonic() + 1

    def list_rules(self):
        return self._get(self._mailbox_path("/rules")).get("items", [])

    def create_rule(self, rule):
        self._pace_mail_write()
        try:
            return self._post(
                self._mailbox_path("/rules"), rule,
            ).get("rule", {})
        finally:
            self._next_mail_write_at = time.monotonic() + 1

    def batch_move(self, message_ids, folder_id):
        for start in range(0, len(message_ids), 50):
            self._post(
                self._mailbox_path("/messages/batch_modify"),
                {
                    "message_ids": message_ids[start:start + 50],
                    "add_folder": str(folder_id),
                },
            )

    def _pace_mail_write(self):
        delay = self._next_mail_write_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def get_attachment_urls(self, message_id, attachment_ids):
        urls = {}
        for start in range(0, len(attachment_ids), 20):
            delay = self._next_attachment_url_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            params = [
                ("attachment_ids", attachment_id)
                for attachment_id in attachment_ids[start:start + 20]
            ]
            try:
                data = self._get(
                    self._mailbox_path(f"/messages/{message_id}/attachments/download_url"),
                    params,
                )
            finally:
                self._next_attachment_url_at = time.monotonic() + 1
            urls.update({
                item.get("attachment_id"): item.get("download_url")
                for item in data.get("download_urls", [])
                if item.get("attachment_id") and item.get("download_url")
            })
        return urls

    def download(self, url, destination):
        response = self.session.get(url, stream=True, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(f"附件下载失败: HTTP {response.status_code}")
        with open(destination, "wb") as output:
            for chunk in response.iter_content(1024 * 256):
                if chunk:
                    output.write(chunk)

    def download_trusted_invoice_link(self, url, destination, expected_extension):
        current = url
        for _ in range(6):
            if not _trusted_invoice_url(current):
                raise RuntimeError("发票链接跳转到非阿里云域名")
            response = self.session.get(
                current, stream=True, allow_redirects=False, timeout=120,
            )
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise RuntimeError("发票链接重定向缺少目标地址")
                current = urljoin(current, location)
                continue
            if response.status_code != 200:
                raise RuntimeError(f"发票链接下载失败: HTTP {response.status_code}")
            content_type = response.headers.get("Content-Type", "").casefold()
            if "text/html" in content_type:
                raise RuntimeError("发票链接返回了网页而不是文件")
            with open(destination, "wb") as output:
                for chunk in response.iter_content(1024 * 256):
                    if chunk:
                        output.write(chunk)
            _validate_invoice_file(destination, expected_extension)
            return _response_filename(response, expected_extension)
        raise RuntimeError("发票链接重定向次数过多")


def safe_filename(filename):
    name = str(filename or "附件").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name or "附件"


def decode_mail_text(value):
    text = str(value or "")
    if not text:
        return ""
    try:
        padded = text + "=" * (-len(text) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8")
    except (ValueError, UnicodeError):
        return text


class _InvoiceLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._href = None
        self._text = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.casefold() == "a" and self._href:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None
            self._text = []


def _sender_address(message):
    return str((message.get("head_from") or {}).get("mail_address", "")).casefold()


def _trusted_invoice_url(url):
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(
        host == suffix[1:] or host.endswith(suffix)
        for suffix in TRUSTED_INVOICE_HOST_SUFFIXES
    )


def extract_invoice_links(message):
    if _sender_address(message) != TRUSTED_INVOICE_SENDER:
        return []
    parser = _InvoiceLinkParser()
    parser.feed(decode_mail_text(message.get("body_html")))
    result = []
    seen_kinds = set()
    message_id = str(message.get("message_id", ""))
    for href, label in parser.links:
        match = re.search(r"(?:下载)?\s*(PDF)\s*发票", label, re.I)
        if not match or not _trusted_invoice_url(href):
            continue
        kind = match.group(1).upper()
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)
        extension = INVOICE_LINK_LABELS[kind]
        source_key = hashlib.sha256(f"{message_id}:{kind}".encode()).hexdigest()
        result.append({
            "id": f"link:{source_key}", "source_type": "body_link",
            "filename": f"阿里云电子发票{extension}", "url": href,
            "expected_extension": extension,
        })
    return result


def _response_filename(response, expected_extension):
    disposition = response.headers.get("Content-Disposition", "")
    message = Message()
    message["content-disposition"] = disposition
    name = safe_filename(message.get_filename()) if message.get_filename() else ""
    if name and Path(name).suffix.casefold() == expected_extension:
        return name
    return f"阿里云电子发票{expected_extension}"


def _validate_invoice_file(path, expected_extension):
    with open(path, "rb") as source:
        head = source.read(16).lstrip()
    valid = expected_extension == ".pdf" and head.startswith(b"%PDF-")
    if not valid:
        raise RuntimeError(f"下载内容不是有效的 {expected_extension[1:].upper()} 文件")


def message_time(message):
    value = message.get("internal_date")
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, CN_TZ)
    except (TypeError, ValueError, OSError):
        return datetime.now(CN_TZ)


def sender_text(message):
    sender = message.get("head_from") or {}
    name = sender.get("name", "")
    address = sender.get("mail_address", "")
    if name and address:
        return f"{name} <{address}>"
    return name or address


def non_inline_attachments(message):
    result = []
    for attachment in message.get("attachments") or []:
        if not attachment.get("is_inline") and attachment.get("id"):
            result.append({**attachment, "filename": safe_filename(attachment.get("filename"))})
    return result


def unique_path(directory, filename):
    path = Path(directory) / filename
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def list_mail(api, limit=20):
    items = []
    for message_id in api.list_message_ids(limit):
        message = api.get_message(message_id)
        items.append({
            "message_id": message_id,
            "date": message_time(message).isoformat(timespec="seconds"),
            "sender": sender_text(message),
            "subject": message.get("subject", ""),
            "attachments": [item.get("filename", "") for item in non_inline_attachments(message)],
        })
    return items


def download_mail(api, message_id, destination):
    message = api.get_message(message_id)
    attachments = non_inline_attachments(message)
    urls = api.get_attachment_urls(message_id, [item["id"] for item in attachments])
    directory = Path(destination).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    saved = []
    for attachment in attachments:
        url = urls.get(attachment["id"])
        if not url:
            raise RuntimeError(f"未获取到附件下载链接: {attachment['filename']}")
        path = unique_path(directory, attachment["filename"])
        temporary = directory / f".{attachment['filename']}.{uuid.uuid4().hex}.part"
        try:
            api.download(url, temporary)
            os.replace(temporary, path)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
        saved.append(str(path))
    return saved


def is_invoice_message(message):
    attachment_names = " ".join(
        str(item.get("filename", "")) for item in message.get("attachments") or []
    )
    text = " ".join((
        str(message.get("subject", "")),
        decode_mail_text(message.get("body_preview")),
        decode_mail_text(message.get("body_plain_text")),
        attachment_names,
    )).casefold()
    return any(keyword.casefold() in text for keyword in KEYWORDS)


def invoice_attachments(message):
    result = []
    for attachment in non_inline_attachments(message):
        if Path(attachment["filename"]).suffix.lower() in INVOICE_EXTENSIONS:
            result.append(attachment)
    return result


def _attachment_source(attachment):
    return {
        **attachment,
        "source_type": "attachment",
        "expected_extension": Path(attachment["filename"]).suffix.casefold(),
    }


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_rows(csv_path):
    if not csv_path.exists():
        return []
    with open(csv_path, newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _write_rows(csv_path, rows):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = csv_path.with_name(f".{csv_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary, "w", newline="", encoding="utf-8-sig") as output:
            writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    field: (
                        "'" + str(row.get(field, ""))
                        if field in CSV_ESCAPE_FIELDS
                        and str(row.get(field, "")).startswith(("=", "+", "-", "@"))
                        else row.get(field, "")
                    )
                    for field in CSV_FIELDS
                })
        os.replace(temporary, csv_path)
    finally:
        if temporary.exists():
            temporary.unlink()


class InvoiceArchiver:
    def __init__(self, api, root=DEFAULT_ROOT):
        self.api = api
        self.root = Path(root).expanduser().resolve()

    def collect(self, limit=100, dry_run=False):
        csv_path = self.root / CSV_NAME
        rows = _read_rows(csv_path)
        known_ids = {
            row.get("来源ID") or row.get("attachment_id")
            for row in rows if row.get("来源ID") or row.get("attachment_id")
        }
        known_hashes = {
            row.get("SHA256"): row.get("保存文件")
            for row in rows if row.get("SHA256") and row.get("保存文件")
        }
        result = {
            "dry_run": dry_run, "scanned": 0, "matched_messages": 0,
            "keyword_matched_messages": 0, "messages_with_attachments": 0,
            "messages_with_body_links": 0, "candidate_attachments": 0,
            "candidate_body_links": 0, "saved": 0, "duplicates": 0,
            "skipped_known": 0, "failed": 0, "candidates": [], "errors": [],
        }
        changed = False

        for message_id in self.api.list_message_ids(limit):
            result["scanned"] += 1
            try:
                message = self.api.get_message(message_id)
                if not is_invoice_message(message):
                    continue
                result["matched_messages"] += 1
                result["keyword_matched_messages"] += 1
                attachments = [_attachment_source(item) for item in invoice_attachments(message)]
                body_links = extract_invoice_links(message)
                if attachments:
                    result["messages_with_attachments"] += 1
                if body_links:
                    result["messages_with_body_links"] += 1
                sources = attachments + body_links
                if not sources:
                    continue
                mail_time = message_time(message)
                directory = self.root / f"{mail_time.year:04d}" / f"{mail_time.month:02d}"
                pending = []
                for source in sources:
                    if source["id"] in known_ids:
                        result["skipped_known"] += 1
                        continue
                    counter = (
                        "candidate_attachments"
                        if source["source_type"] == "attachment"
                        else "candidate_body_links"
                    )
                    result[counter] += 1
                    pending.append(source)
                    if dry_run:
                        result["candidates"].append({
                            "message_id": message_id,
                            "subject": message.get("subject", ""),
                            "source_type": source["source_type"],
                            "filename": source["filename"],
                            "target": str(unique_path(directory, source["filename"])),
                        })
                if dry_run or not pending:
                    continue

                attachment_ids = [
                    item["id"] for item in pending
                    if item["source_type"] == "attachment"
                ]
                urls = self.api.get_attachment_urls(message_id, attachment_ids)
                directory.mkdir(parents=True, exist_ok=True)
                for source in pending:
                    url = (
                        urls.get(source["id"])
                        if source["source_type"] == "attachment"
                        else source["url"]
                    )
                    if not url:
                        result["failed"] += 1
                        result["errors"].append(f"{source['filename']}: 未获取到下载链接")
                        continue
                    temporary = directory / f".{source['filename']}.{uuid.uuid4().hex}.part"
                    try:
                        filename = source["filename"]
                        if source["source_type"] == "attachment":
                            self.api.download(url, temporary)
                        else:
                            filename = self.api.download_trusted_invoice_link(
                                url, temporary, source["expected_extension"],
                            )
                        digest = _sha256(temporary)
                        existing = known_hashes.get(digest)
                        if existing:
                            temporary.unlink()
                            saved_path, status = existing, "重复文件"
                            result["duplicates"] += 1
                        else:
                            destination = unique_path(directory, filename)
                            os.replace(temporary, destination)
                            saved_path, status = str(destination), "已保存"
                            known_hashes[digest] = saved_path
                            result["saved"] += 1
                        rows.append({
                            "邮箱": getattr(self.api, "mailbox_id", "me"),
                            "邮件日期": mail_time.isoformat(timespec="seconds"),
                            "发件人": sender_text(message),
                            "主题": message.get("subject", ""),
                            "原文件名": filename,
                            "保存文件": saved_path,
                            "SHA256": digest,
                            "message_id": message_id,
                            "attachment_id": (
                                source["id"] if source["source_type"] == "attachment" else ""
                            ),
                            "来源类型": source["source_type"],
                            "来源ID": source["id"],
                            "处理状态": status,
                        })
                        known_ids.add(source["id"])
                        changed = True
                    except Exception as error:
                        if temporary.exists():
                            temporary.unlink()
                        result["failed"] += 1
                        result["errors"].append(f"{source['filename']}: {error}")
            except Exception as error:
                result["failed"] += 1
                result["errors"].append(f"{message_id}: {error}")

        if changed:
            _write_rows(csv_path, rows)
        result["summary_csv"] = str(csv_path)
        return result


def parse_collect_args(arguments):
    parser = argparse.ArgumentParser(prog="feishu.py invoice-collect")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--mailbox", default="me")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(arguments)
