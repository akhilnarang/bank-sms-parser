# AGENTS.md — bank-sms-parser

## Quick reference

- **Run setup:** `uv sync`
- **Run tests:** `uv run pytest -q`
- **Run lint:** `uv run ruff check`
- **Run types:** `uv run ty check`
- **Python:** 3.14+ · **Package manager:** uv
- **PEP 758 is valid here.** Do not "fix" parenthesis-free multi-except syntax for 3.14.

## Project layout

- Flat package layout: `bank_sms_parser/`
- Public API stays in `bank_sms_parser/__init__.py` and `bank_sms_parser/api.py`
- Parsing helpers live in `bank_sms_parser/parsing/`
  - `dates.py` → `parse_date`, `parse_datetime`, `received_at_to_ist`
    (HDFC's `2026-05-02:00:17:56` colon-separator is pre-normalized;
    `dayfirst=True` for Indian formats)
  - `amounts.py` → `parse_amount` (bare numerics), `parse_money`
    (requires currency prefix; recognizes `Rs.` / `INR` / 3-letter ISO)
  - `text.py` → `normalize_whitespace`, `extract_card_mask`,
    `extract_account_mask`
- Bank parsers live in `bank_sms_parser/parsers/`
  - Single-shape banks: `parsers/{bank}.py`
  - Multi-shape banks: `parsers/{bank}/` subpackage (one parser
    class per shape)
  - `parsers/__init__.py` contains the explicit `PARSERS` registry

## Parser architecture

- `api.parse_sms(bank, body, *, sender=None, received_at=None)`
  uses the explicit bank registry.
- Registry entries are **bank dispatcher classes** (`HdfcParser`,
  `IciciParser`, etc.), not individual SMS-shape parsers.
- Each bank module/subpackage owns:
  - one or more `BaseSmsParser` subclasses with stable `email_type` strings
  - `_PARSERS` ordered tuple (first match wins; **even single-parser
    banks declare the tuple**)
  - a bank dispatcher class (`{Bank}Parser`) inheriting `BankSmsParser`
  - module/subpackage-level
    `parse(body, *, sender=None, received_at=None)` wrapper that
    forwards both kwargs to the dispatcher
- Preserve external imports like
  `from bank_sms_parser.parsers.icici import IciciParser`.

## Adding a new bank or SMS shape

> Use `.agents/skills/add-bank-sms-parser/SKILL.md`.

Checklist:

1. Prefer `bank_sms_parser/parsers/{bank}/` when the bank has multiple
   distinct SMS shapes; otherwise `parsers/{bank}.py` is fine.
2. Add one `BaseSmsParser` subclass per SMS shape (with cosmetic
   variants of the same shape handled via multiple compiled regexes
   inside one class — see `parsers/onecard/charge.py`).
3. Keep `email_type` values stable and bank-prefixed.
4. Add parser instances to `_PARSERS` in specificity order.
5. Expose a bank dispatcher class (`{Bank}Parser`) and a module-level
   `parse(body, *, sender=None, received_at=None)`.
6. Register the dispatcher in `bank_sms_parser/parsers/__init__.py`.
7. Reuse helpers from `bank_sms_parser.parsing/` before adding ad-hoc
   regex helpers.
8. Add fixture-based tests in `tests/fixtures/sms/{bank}/...` and a
   parametrized case in `tests/test_new_parsers.py`.

## Critical rules

- **Never rename `email_type` values.** `bank-email-fetcher` will
  store these verbatim.
- **Preserve public API compatibility:** `parse_sms`, `SUPPORTED_BANKS`,
  `ParsedSms`, exception types, and bank-level dispatcher imports.
- **Never use real personal data** in tests, docs, comments, or
  fixtures (see `tests/test_repository_hygiene.py`).
- **`raw_description`** is debug-only and excluded from dumps/repr by
  default.
- **`direction`** can be `"debit"`, `"credit"`, or `"declined"`.
- **`received_at` is UTC.** Always convert to `Asia/Kolkata` via
  `received_at_to_ist` before extracting `.date()` / `.time()`.
- **`parse_money` requires a currency prefix** — bare numerics use
  `parse_amount`. Do not silently default to INR for amounts that
  arrived without a prefix.
- **OneCard** is a fintech that ships many cosmetic phrasings of the
  same event; one parser class with multiple compiled regexes is the
  pattern. Do not split into one class per phrasing.

## Cross-project

When `bank-email-fetcher` adopts the SMS-pipeline (Part 2-B; not in
this package), wire the SMS poller to call `parse_sms(bank, body,
sender=..., received_at=...)` and store results analogously to the
email pipeline.
