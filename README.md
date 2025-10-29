# Telegram to WeChat (WeCom) forwarder

该项目演示如何实时将 Telegram 频道/群组消息转发到企业微信（WeCom）机器人，帮助你第一时间在微信生态中收到提醒。

## 功能特点

- 使用 [Telethon](https://docs.telethon.dev) 监听 Telegram 频道或群组的最新消息；
- 将消息内容格式化后，通过企业微信自建机器人 Webhook 推送；
- 支持在环境变量中配置监听频道、会话文件以及 @ 的企业微信成员列表。

## 准备工作

1. [申请 Telegram API ID 与 API Hash](https://my.telegram.org/apps)；
2. 创建企业微信自建应用或群机器人，并获取 Webhook `key`；
3. 准备一台可以长时间运行脚本的机器（服务器、NAS、云函数等）。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置环境变量

```bash
export TELEGRAM_API_ID=1234567
export TELEGRAM_API_HASH="your_api_hash"
export TELEGRAM_CHANNEL="@channel_or_group_username"
# 自定义 Telethon session 名称（可选，默认 telegramtowechat）
export TELEGRAM_SESSION="telegramtowechat.session"

# 企业微信机器人 webhook key
export WECOM_WEBHOOK_KEY="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# 需要 @ 的成员列表（可选，多个成员用逗号分隔）
export WECOM_MENTIONED_LIST="UserID1,UserID2"
```

> **提示**：第一次运行时需要在当前目录下生成 Telegram 会话文件，会弹出短信验证码或 Telegram App 认证，请按照提示完成。

## 运行

```bash
python forwarder.py
```

脚本启动后会自动监听 `TELEGRAM_CHANNEL` 对应的频道/群组，将新消息推送到企业微信。

## 自定义开发

- 如需自定义消息格式，可修改 `forwarder.py` 中的 `format_message` 函数；
- 如果你想转发到企业微信应用而非机器人，可将 `WeComMessenger.send_text` 中的调用改为企业微信应用消息接口。

## 故障排查

- 确保服务器能够同时访问 Telegram 与企业微信接口；
- 检查环境变量是否正确设置，尤其是频道名称前是否带 `@`；
- 查看程序日志（默认 INFO 级别）定位发送失败原因。

