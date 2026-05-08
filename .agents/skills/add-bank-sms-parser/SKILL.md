---
name: add-bank-sms-parser
description: Add a new bank SMS parser or a new SMS shape to an existing bank.
---

# Add or Update a Bank SMS Parser

Arguments: `$ARGUMENTS` — bank slug and one or more sample SMS bodies
(verbatim, including TRAI sender ID and ISO `received_at` if known).

## Read first

- `AGENTS.md`
- `bank_sms_parser/models.py`
- `bank_sms_parser/parsers/base.py`
- `bank_sms_parser/api.py`
- `bank_sms_parser/parsers/__init__.py`
- One existing parser module/subpackage for the closest target shape

## Inspect the SMS first — MANDATORY

Do not write parser code before reading the real SMS body verbatim.
SMS bodies are short, but bank templates vary in subtle ways (date
format, mask format, ordering of clauses). Skipping this step produces
parsers that match imagined structure and silently drop fields.

From each body, identify:

- which fields are present (amount, direction, date/time, counterparty,
  account/card mask, reference, channel, balance/avl-limit)
- how each is encoded (`Rs.`/`INR`, `XX1234`/`x1234`/`*XX1234`, date
  format, `IMPS:`/`RRN:`/`UPI Ref`, `Bal Rs.`/`Avl Limit:`/`Available
  limit`)
- unique markers that distinguish this SMS shape from the bank's other
  shapes
- whether a `received_at` from the forwarder is needed as a date
  fallback

## Implementation checklist

1. Use `bank_sms_parser/parsing/` helpers before ad-hoc regex:
   `parse_date`, `parse_datetime`, `parse_amount`, `parse_money`,
   `received_at_to_ist`, `normalize_whitespace`, `extract_card_mask`,
   `extract_account_mask`.
2. Each parser class subclasses `BaseSmsParser` and implements
   `parse(body: str, *, sender: str | None = None,
   received_at: datetime | None = None) -> ParsedSms`.
3. Build results as
   `ParsedSms(email_type=..., bank=..., transaction=SmsTransactionAlert(...))`.
   `SmsTransactionAlert.amount` requires a `Money`. Wrap bare numerics
   as `Money(amount=parse_amount(match.group("amount")), currency="INR")`;
   use `parse_money(...)` only when the captured text already contains
   the currency prefix (`parse_money` itself returns `Money`).
   `raw_description` is debug-only and excluded from dump/repr — do not
   stash real SMS content in serialized fields.
4. Each bank module/package owns:
   - one `BaseSmsParser` subclass per **distinct** SMS shape with a
     stable `email_type` string
   - one parser class with **multiple compiled regexes** for cosmetic
     phrasings of the same event (e.g. OneCard's "bill cleared" /
     "spent" / "paid <CCY>" all share
     `onecard_cc_transaction_alert`) — do not split into one class
     per phrasing
   - a `_PARSERS` ordered tuple of parser instances (first match wins,
     even when there is only one parser)
   - a `{Bank}Parser(BankSmsParser)` dispatcher with
     `bank = "{slug}"` and `parsers = _PARSERS`
   - module/package-level
     `parse(body, *, sender=None, received_at=None)` that forwards
     both keyword args to the dispatcher
5. Single file (`parsers/{bank}.py`) and subpackage
   (`parsers/{bank}/`) layouts are both valid: `slice.py` and
   `hdfc.py` are multi-shape single files; `icici/` and `onecard/`
   are subpackages. Reach for a subpackage when the bank is large or
   splits naturally by shape; otherwise a single file is fine.
6. Keep `email_type` stable and bank-prefixed (e.g.
   `hdfc_dc_transaction_alert`). `bank-email-fetcher` stores these
   values verbatim — never rename.
7. Register the dispatcher by adding `"{slug}": {Bank}Parser` to the
   `PARSERS` dict in `bank_sms_parser/parsers/__init__.py`.
   `api.SUPPORTED_BANKS = tuple(PARSERS)` and the CLI bank list
   follow automatically.
8. Add fixture-based pytest coverage:
   - positive fixtures at `tests/fixtures/sms/{bank}/{slug}.txt`
     plus a parametrized case in `tests/test_new_parsers.py`
   - for known non-transaction or intentionally stubbed shapes,
     drop the body at `tests/fixtures/sms/{bank}/negative/{slug}.txt`
     and add it to `test_real_negative_fixtures_raise_parse_error`

## `_PARSERS` ordering

First match wins. Order matters:

1. **Specific parsers first** — those with unique markers.
2. **Broad parsers next** — reliable but match more shapes.
3. **`ParserStubError` stubs at the very end**, so they never shadow
   real parsers.

## SMS guardrails — MANDATORY

Indian bank SMSes share TRAI senders across many message types. A
naive parser will happily extract an "amount" from an OTP and emit a
fake transaction. Every parser must:

- Reject OTP / login / mandate / promotional / service-info /
  reminder messages by raising `ParseError` (or, if the shape is
  well-known and intentionally unimplemented, `ParserStubError`). Do
  not parse them as transaction alerts.
- Treat the SMS body as authoritative. Every parser requires at
  minimum `amount` and `direction`; transaction/spend alerts also
  require `account_mask` or `card_mask`; payment-received alerts may
  omit the mask if the bank's template does not include one. If any
  required field is missing — including because the body looks
  truncated — raise `ParseError`. Do not fabricate.
- Infer `direction` from the verb (`debit`: debited, spent, paid,
  withdrawn, purchased; `credit`: credited, received, refunded,
  reversed; `declined`: declined, failed). Reject the SMS if no
  canonical verb is present.
- Use the optional `sender` argument as a *secondary* signal at most
  (e.g. to disambiguate two ICICI shapes); never as the sole evidence
  that an SMS is a transaction alert.

## Date/time fallback

If the SMS body has no usable date, parsers must accept the optional
`received_at` argument and use it as the fallback for
`transaction_date` / `transaction_time`. `received_at` is a UTC
datetime per Part 1's contract; convert to `Asia/Kolkata` via
`received_at_to_ist` (from `bank_sms_parser.parsing`) **before**
extracting `.date()` / `.time()`. An SMS that arrived at 02:30 IST
will otherwise land on the previous UTC day. Do not invent a date
from `today()`; either use what the body says, what the forwarder
gave us (IST-converted), or leave the field `None`.

## Rules

- Raise `ParseError` (or `ParserStubError` for known-but-unimplemented
  shapes). Never return `None` — the dispatcher needs the exception to
  try the next parser.
- Keep public compatibility: `parse_sms`, `SUPPORTED_BANKS`,
  exceptions, and bank-level imports
  (`from bank_sms_parser.parsers.{bank} import {Bank}Parser`).
- Never commit real personal or financial data. Use the stable fake
  conventions already in fixtures: card/account masks `XX0000` /
  `x0000` / `xx0000` / `0000`; reference numbers `000000000000`;
  customer names `Customer` (`Hi Akhil` → `Hi Customer`); fake
  merchants like `SampleSubs Monthly`. Anonymize VPAs, phone
  numbers, and bank short-links the same way.
- Python is 3.14+. Do **not** "fix" parenthesis-free multi-except
  syntax (PEP 758) — see `AGENTS.md`.

## Final check

After implementation, from the package root, run:

    uv sync               # only if deps are not yet installed
    uv run pytest -q
    uv run ruff check
    uv run ty check

All must pass before commit. Match conventions in `AGENTS.md`.
