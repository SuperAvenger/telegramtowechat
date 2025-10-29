"""Forward Telegram channel messages to WeCom (WeChat Work) in real time."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp
from telethon import TelegramClient, events


LOGGER = logging.getLogger("telegramtowechat")


@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    session: str
    channel: str

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        try:
            api_id = int(os.environ["TELEGRAM_API_ID"])
            api_hash = os.environ["TELEGRAM_API_HASH"]
            channel = os.environ["TELEGRAM_CHANNEL"]
        except KeyError as exc:  # pragma: no cover - just defensive
            missing = exc.args[0]
            raise RuntimeError(
                f"Missing required environment variable: {missing}"
            ) from exc

        session = os.environ.get("TELEGRAM_SESSION", "telegramtowechat")

        return cls(api_id=api_id, api_hash=api_hash, session=session, channel=channel)


@dataclass
class WeComConfig:
    webhook_key: str
    mentioned_list: Optional[list[str]] = None

    @classmethod
    def from_env(cls) -> "WeComConfig":
        try:
            webhook_key = os.environ["WECOM_WEBHOOK_KEY"]
        except KeyError as exc:  # pragma: no cover
            raise RuntimeError(
                "Missing required environment variable: WECOM_WEBHOOK_KEY"
            ) from exc

        mentioned_list: Optional[list[str]] = None
        raw_mentions = os.environ.get("WECOM_MENTIONED_LIST")
        if raw_mentions:
            mentioned_list = [item.strip() for item in raw_mentions.split(",") if item.strip()]

        return cls(webhook_key=webhook_key, mentioned_list=mentioned_list)


class WeComMessenger:
    def __init__(self, config: WeComConfig) -> None:
        self._config = config
        self._webhook_url = (
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
            f"{config.webhook_key}"
        )

    async def send_text(self, text: str) -> None:
        payload: dict[str, Any] = {"msgtype": "text", "text": {"content": text}}
        if self._config.mentioned_list:
            payload["text"]["mentioned_list"] = self._config.mentioned_list

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(
                        f"WeCom webhook responded with status {response.status}: {body}"
                    )


def format_message(event: events.NewMessage.Event) -> str:
    sender = ""
    if event.chat and getattr(event.chat, "title", None):
        sender = event.chat.title
    elif event.chat and getattr(event.chat, "username", None):
        sender = event.chat.username

    parts = []
    if sender:
        parts.append(f"📣 {sender}")

    message_text = event.raw_text.strip()
    if message_text:
        parts.append(message_text)
    else:
        parts.append("[Telegram消息无文本内容]")

    if event.message and event.message.date:
        parts.append(event.message.date.strftime("%Y-%m-%d %H:%M:%S"))

    if (
        event.message
        and event.message.id
        and event.chat
        and getattr(event.chat, "username", None)
    ):
        parts.append(f"https://t.me/{event.chat.username}/{event.message.id}")

    return "\n".join(parts)


async def run_forwarder() -> None:
    logging.basicConfig(level=logging.INFO)

    tg_config = TelegramConfig.from_env()
    wecom_config = WeComConfig.from_env()
    messenger = WeComMessenger(wecom_config)

    client = TelegramClient(tg_config.session, tg_config.api_id, tg_config.api_hash)

    await client.start()

    LOGGER.info("Listening for messages in %s", tg_config.channel)

    @client.on(events.NewMessage(chats=tg_config.channel))
    async def handler(event: events.NewMessage.Event) -> None:
        try:
            text = format_message(event)
            await messenger.send_text(text)
            LOGGER.info("Forwarded message %s", event.id)
        except Exception:  # pragma: no cover
            LOGGER.exception("Failed to forward Telegram message")

    await client.run_until_disconnected()


def main() -> None:
    try:
        asyncio.run(run_forwarder())
    except KeyboardInterrupt:  # pragma: no cover
        LOGGER.info("Forwarder interrupted by user")


if __name__ == "__main__":
    main()

