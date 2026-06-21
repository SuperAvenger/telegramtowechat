# Roadmap

## Decision Gate

Implementation should begin only after choosing a supported source and destination. Prefer a Telegram Bot API source and an Enterprise WeChat group robot destination because both have documented, revocable credentials.

## First Milestone

- Define a normalized message model and explicit handling for text, links, and unsupported media.
- Add allowlists, rate limits, deduplication, redacted structured logs, and retry with backoff.
- Provide a dry-run mode and fixture-based adapter tests before enabling delivery.

## Later

- Add pluggable source and destination adapters.
- Expose health and delivery-status reads through MCP only if there is a real ChatGPT workflow.
