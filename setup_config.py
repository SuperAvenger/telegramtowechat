"""Interactive local configuration writer. Secrets never leave this computer."""

from __future__ import annotations

import getpass
import shlex
from pathlib import Path


ENV_FILE = Path(__file__).with_name(".env")


def ask(prompt: str, *, secret: bool = False) -> str:
    while True:
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if value:
            return value
        print("此项不能为空，请重新输入。")


def main() -> None:
    print("\nTelegram → 企业微信首次配置")
    print("信息只会写入当前目录的 .env，不会上传。\n")

    api_id = ask("Telegram API_ID（纯数字）：")
    if not api_id.isdigit() or int(api_id) <= 0:
        raise SystemExit("API_ID 格式不正确，应为正整数。")
    api_hash = ask("Telegram API_HASH（输入时隐藏）：", secret=True)
    channel = ask("新闻频道用户名（例如 @BBCWorld）：")
    webhook = ask("企业微信群机器人 Webhook（输入时隐藏）：", secret=True)
    if "qyapi.weixin.qq.com/cgi-bin/webhook/send" not in webhook:
        raise SystemExit("Webhook 地址格式看起来不正确，请从企业微信群机器人页面重新复制。")

    values = {
        "TELEGRAM_API_ID": api_id,
        "TELEGRAM_API_HASH": api_hash,
        "TELEGRAM_CHANNELS": channel,
        "WECOM_WEBHOOK_URL": webhook,
        "TELEGRAM_SESSION": "telegram_to_wecom",
        "DRY_RUN": "0",
        "LOG_LEVEL": "INFO",
    }
    content = "".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items())
    ENV_FILE.write_text(content, encoding="utf-8")
    ENV_FILE.chmod(0o600)
    print(f"\n配置完成：{ENV_FILE}")
    print("即将启动。首次登录需要 Telegram 手机号和验证码。\n")


if __name__ == "__main__":
    main()
