import asyncio
from types import SimpleNamespace

import pytest

from forwarder import (
    MessageDeduper,
    Settings,
    chunks,
    image_payload,
    forward_media,
    media_label,
    parse_channels,
    wecom_upload_url,
)


def test_parse_channels_supports_username_and_numeric_id():
    assert parse_channels("news, @alerts, -100123") == ["@news", "@alerts", -100123]


def test_parse_channels_rejects_empty_value():
    with pytest.raises(ValueError):
        parse_channels(" , ")


def test_chunks_preserves_all_text():
    text = "a" * 15 + "\n" + "b" * 15
    parts = list(chunks(text, 20))
    assert "".join(parts) == text
    assert all(len(part.encode("utf-8")) <= 20 for part in parts)


def test_chunks_respects_utf8_byte_limit():
    text = "中文消息" * 10
    parts = list(chunks(text, 20))
    assert "".join(parts) == text
    assert all(len(part.encode("utf-8")) <= 20 for part in parts)


def test_chunks_rejects_invalid_limit():
    with pytest.raises(ValueError):
        list(chunks("a", 0))


def test_media_label():
    assert media_label(SimpleNamespace(photo=True)) == "[图片]"
    assert media_label(SimpleNamespace(photo=None, video=None, voice=None, document=None, media=None)) == ""


def test_image_payload_contains_required_base64_and_md5():
    payload = image_payload(b"image-data")
    assert payload["msgtype"] == "image"
    assert payload["image"]["base64"] == "aW1hZ2UtZGF0YQ=="
    assert len(payload["image"]["md5"]) == 32


def test_wecom_upload_url_reuses_webhook_key_without_exposing_other_query_values():
    url = wecom_upload_url(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret-key&ignored=yes"
    )
    assert url == (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media"
        "?key=secret-key&type=file"
    )


def test_wecom_upload_url_rejects_non_wecom_host():
    with pytest.raises(ValueError):
        wecom_upload_url("https://example.test/send?key=secret")


def test_forward_media_routes_photo_and_file_without_network():
    class FakeSender:
        def __init__(self):
            self.calls = []

        async def send_image(self, data):
            self.calls.append(("image", data))

        async def send_file(self, data, filename):
            self.calls.append(("file", data, filename))

    class FakeMessage:
        id = 7
        media = True

        def __init__(self, photo, name):
            self.photo = photo
            self.file = SimpleNamespace(size=4, name=name)

        async def download_media(self, file):
            assert file is bytes
            return b"data"

    sender = FakeSender()
    photo_result = asyncio.run(forward_media(FakeMessage(True, None), sender, 10))
    file_result = asyncio.run(forward_media(FakeMessage(False, "report.pdf"), sender, 10))

    assert photo_result == "图片已转发"
    assert file_result == "文件已转发：report.pdf"
    assert sender.calls == [("image", b"data"), ("file", b"data", "report.pdf")]


def test_forward_media_rejects_declared_oversize_before_download():
    message = SimpleNamespace(file=SimpleNamespace(size=21), photo=True)
    with pytest.raises(ValueError, match="超过大小限制"):
        asyncio.run(forward_media(message, SimpleNamespace(), 20))


def test_settings_rejects_invalid_api_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "not-a-number")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_CHANNELS", "@news")
    monkeypatch.setenv("WECOM_WEBHOOK_URL", "https://example.test")
    with pytest.raises(ValueError, match="必须是整数"):
        Settings.from_env()


def test_deduper_persists_successful_delivery_across_restart(tmp_path):
    state_file = tmp_path / "state.json"
    deduper = MessageDeduper(state_file, limit=100)
    assert not deduper.contains("message-1")

    deduper.mark_delivered("message-1")
    restored = MessageDeduper(state_file, limit=100)

    assert restored.contains("message-1")


def test_deduper_does_not_record_unmarked_failed_message(tmp_path):
    state_file = tmp_path / "state.json"
    MessageDeduper(state_file, limit=100)

    restored = MessageDeduper(state_file, limit=100)
    assert not restored.contains("failed-message")
