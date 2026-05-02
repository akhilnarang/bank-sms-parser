# bank-sms-parser

Parse Indian bank transaction-alert SMS bodies into structured `ParsedSms`.
Sibling library to `bank-email-parser`, mirroring its architecture for the
text-message medium.

## Usage

```python
from bank_sms_parser import parse_sms

result = parse_sms(
    bank="hdfc",
    body="Spent Rs.3000 From HDFC Bank Card x0000 At MERCHANT On 2026-05-02:00:17:56 Bal Rs.142.26 ...",
)
print(result.email_type)            # "hdfc_dc_transaction_alert"
print(result.transaction.amount)    # Money(amount=Decimal("3000"), currency="INR")
```

## CLI

```bash
echo "<sms body>" | uv run bank-sms-parser --bank hdfc
```

## Adding a new bank

See `.agents/skills/add-bank-sms-parser/SKILL.md`.
