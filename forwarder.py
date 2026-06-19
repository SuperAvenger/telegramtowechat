"""Low-latency Telegram channel to WeCom group robot forwarder."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import aiohttp
from telethon import TelegramClient, events


LOG = logging.getLogger("telegramtowechat")
WECOM_TEXT_LIMIT = 1900
SECRET_RE = re.compile(r"(key=)[^&\s]+", re.IGNORECASE)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"缺少环境变量 {name}")
    return value


def parse_channels(value: str) -> list[int | str]:
    channels: list[int | str] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        try:
            channels.append(int(item))
        except ValueError:
            channels.append(item if item.startswith("@") else f"@{item}")
    if not channels:
        raise ValueError("TELEGRAM_CHANNELS 至少需要一个频道")
    return channels


def chunks(text: str, limit: int = WECOM_TEXT_LIMIT) -> Iterable[str]:
    """Split by UTF-8 bytes without losing content or breaking characters."""
    if limit < 1:
        raise ValueError("limit 必须大于 0")
    start = 0
    while start < len(text):
        byte_count = 0
        end = start
        last_newline = -1
        while end < len(text):
            char_size = len(text[end].encode("utf-8"))
            if byte_count + char_size > limit:
                break
            byte_count += char_size
            if text[end] == "\n":
                last_newline = end
            end += 1
        if end == start:
            raise ValueError("limit 小于单个 UTF-8 字符所需字节数")
        if end < len(text) and last_newline >= start + (end - start) // 2:
            end = last_newline + 1
        yield text[start:end]
        start = end


def media_label(message: object) -> str:
    if getattr(message, "photo", None):
        return "[图片]"
    if getattr(message, "video", None):
        return "[视频]"
    if getattr(message, "voice", None):
        return "[语音]"
    if getattr(message, "document", None):
        return "[文件]"
    if getattr(message, "media", None):
        return "[媒体消息]"
    return ""


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    channels: list[int | str]
    webhook_url: str
    session_name: str
    dry_run: bool
    dedupe_state_file: str
    dedupe_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            api_id = int(require_env("TELEGRAM_API_ID"))
        except ValueError as exc:
            raise ValueError("TELEGRAM_API_ID 必须是整数") from exc
        if api_id <= 0:
            raise ValueError("TELEGRAM_API_ID 必须大于 0")
        session_name = os.getenv("TELEGRAM_SESSION", "telegram_to_wecom").strip()
        if not session_name:
            raise ValueError("TELEGRAM_SESSION 不能为空")
        return cls(
            api_id=api_id,
            api_hash=require_env("TELEGRAM_API_HASH"),
            channels=parse_channels(require_env("TELEGRAM_CHANNELS")),
            webhook_url=require_env("WECOM_WEBHOOK_URL"),
            session_name=session_name,
            dry_run=os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"},
            dedupe_state_file=os.getenv("DEDUPE_STATE_FILE", ".forwarder-state.json").strip(),
            dedupe_limit=max(100, int(os.getenv("DEDUPE_LIMIT", "10000"))),
        )


class MessageDeduper:
    """Bounded, restart-safe record of successfully delivered messages."""

    def __init__(self, path: str | Path, limit: int = 10_000) -> None:
        self.path = Path(path)
        self.limit = max(100, limit)
        self.keys: list[str] = []
        self._key_set: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            keys = payload.get("delivered", []) if isinstance(payload, dict) else []
            self.keys = [str(key) for key in keys[-self.limit:]]
            self._key_set = set(self.keys)
        except (OSError, json.JSONDecodeError, TypeError):
            LOG.warning("无法读取去重状态，将从空状态启动：%s", self.path)

    def contains(self, key: str) -> bool:
        return key in self._key_set

    def mark_delivered(self, key: str) -> None:
        if key in self._key_set:
            return
        self.keys.append(key)
        self._key_set.add(key)
        if len(self.keys) > self.limit:
            removed = self.keys[:-self.limit]
            self.keys = self.keys[-self.limit:]
            self._key_set.difference_update(removed)
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps({"version": 1, "delivered": self.keys}, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(self.path)


class WeComSender:
    def __init__(self, webhook_url: str, dry_run: bool = False) -> None:
        self.webhook_url = webhook_url
        self.dry_run = dry_run
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "WeComSender":
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.session:
            await self.session.close()

    async def send(self, text: str) -> None:
        for part in chunks(text):
            await self._send_part(part)

    async def _send_part(self, text: str) -> None:
        if self.dry_run:
            LOG.info("DRY_RUN: %s", text)
            return
        assert self.session is not None
        payload = {"msgtype": "text", "text": {"content": text}}
        for attempt in range(4):
            try:
                async with self.session.post(self.webhook_url, json=payload) as response:
                    data = await response.json(content_type=None)
                    if response.status == 200 and data.get("errcode") == 0:
                        return
                    error = f"HTTP {response.status}, errcode={data.get('errcode')}: {data.get('errmsg')}"
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                error = str(exc)
            if attempt == 3:
                raise RuntimeError(f"企业微信推送失败: {error}")
            await asyncio.sleep(0.5 * (2**attempt))


def message_url(username: str | None, message_id: int) -> str:
    return f"https://t.me/{username}/{message_id}" if username else ""


async def run(settings: Settings) -> None:
    client = TelegramClient(settings.session_name, settings.api_id, settings.api_hash)
    deduper = MessageDeduper(settings.dedupe_state_file, settings.dedupe_limit)

    async with WeComSender(settings.webhook_url, settings.dry_run) as sender:
        @client.on(events.NewMessage(chats=settings.channels))
        async def handle(event: events.NewMessage.Event) -> None:
            message = event.message
            chat = await event.get_chat()
            chat_id = str(getattr(chat, "id", event.chat_id))
            dedupe_key = hashlib.sha256(f"{chat_id}:{message.id}".encode()).hexdigest()
            if deduper.contains(dedupe_key):
                return

            title = getattr(chat, "title", None) or getattr(chat, "username", None) or chat_id
            body = (message.raw_text or "").strip()
            media = media_label(message)
            content = "\n".join(part for part in (media, body) if part) or "[空消息]"
            url = message_url(getattr(chat, "username", None), message.id)
            output = f"【Telegram · {title}】\n{content}"
            if url:
                output += f"\n\n原消息：{url}"
            try:
                await sender.send(output)
                deduper.mark_delivered(dedupe_key)
                LOG.info("已推送 channel=%s message_id=%s", chat_id, message.id)
            except Exception:
                LOG.exception("推送失败 channel=%s message_id=%s", chat_id, message.id)

        await client.start()
        me = await client.get_me()
        LOG.info("Telegram 已连接：%s；监听 %s", getattr(me, "username", None) or me.id, settings.channels)
        await client.run_until_disconnected()


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = Settings.from_env()
        asyncio.run(run(settings))
    except (ValueError, TypeError) as exc:
        LOG.error("配置错误：%s", SECRET_RE.sub(r"\1***", str(exc)))
        return 2
    except KeyboardInterrupt:
        LOG.info("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
