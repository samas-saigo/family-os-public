# Deduplication Strategy

## Why this matters

A multi-email household will receive the same real-world event multiple times.

Examples:
- both spouses receive the same reservation
- one spouse forwards the message
- reminder email repeats the original
- calendar auto-creates the event
- a receipt appears in email and Drive
- joint financial transactions appear in two linked views

## Matching hierarchy

### Level 1 — exact provider identity
Same `source_account + provider_object_id`.

Action: identical.

### Level 2 — exact content
Same normalized content hash.

Action: auto-link to one canonical entity.

### Level 3 — strong domain key
Examples:
- confirmation number
- policy number
- order number
- reservation ID
- VIN + service date
- merchant + amount + timestamp

Action: usually auto-link.

### Level 4 — semantic match
Examples:
- same hotel, same dates, same traveler
- reminder message referencing prior booking

Action:
- auto-link only at very high confidence
- otherwise send to review queue

## Never dedupe merely because

- subject lines match
- sender matches
- amount matches
- date matches

Those are weak signals by themselves.
