from types import SimpleNamespace

import pytest

from forwarder import MessageDeduper, Settings, chunks, media_label, parse_channels


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
