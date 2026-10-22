# Connector interfaces

Every provider adapter should implement conceptually:

```python
list_accounts()
fetch_changes(cursor)
normalize(raw_record)
```

Provider authentication belongs outside domain logic.
