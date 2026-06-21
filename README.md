# Telegram → 企业微信实时转发

通过 Telethon 用户会话实时监听指定 Telegram 频道，把新消息推送到企业微信群机器人。正常网络条件下通常是秒级到达；实际延迟取决于 Telegram、部署机网络和企业微信。

## 为什么使用用户会话

Telegram Bot 只能读取它有权访问的频道，通常需要把 Bot 加为频道管理员。用户会话可以监听该账号已经加入的公开或私有频道，更适合“订阅别人的频道”。请仅转发你有权访问和处理的内容。

## 准备

1. 在 `my.telegram.org` 创建应用，取得 `api_id` 和 `api_hash`。
2. 在企业微信群中添加“群机器人”，复制 Webhook 地址。
3. 安装 Python 3.10+，然后执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`。`TELEGRAM_CHANNELS` 可填逗号分隔的 `@频道用户名` 或 `-100...` 频道 ID。

### macOS 一键启动

在 Finder 中打开项目目录，双击 `启动转发.command`。首次启动会自动安装依赖并依次询问配置。macOS 如果阻止首次打开，请右键文件选择“打开”。

敏感信息保存在权限为仅当前用户可读的 `.env` 文件中，不要把该文件发给任何人。

## 运行

```bash
./run.sh
```

首次运行会要求输入 Telegram 手机号、验证码；如账号启用了两步验证，还会询问密码。之后凭据保存在本机 `.session` 文件中，无需反复登录。

先把 `DRY_RUN=1` 可只打印、不推送。确认无误后改为 `0`。生产环境建议使用 systemd、Docker 或云服务器常驻运行；电脑休眠时不会转发。

## 当前能力与边界

- 文本、链接、图片和不超过 20MB 的文件即时推送；公开频道附原消息链接。
- 长消息自动分段，网络错误指数退避重试。
- 成功投递记录会持久化，程序重启后仍能去重；失败消息不会提前标记，可在后续事件中重试。
- 图片使用企业微信图片消息；视频、语音和文档作为文件上传。超限或失败时保留媒体提示和原消息链接。
- Webhook 泄露后任何人都可能向群内发消息；`.env`、`.session` 绝不能提交到 Git。

## 测试

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```
