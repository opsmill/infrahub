---
paths:
  - "backend/**/*.py"
---

# Several database queries of the same shape

Applies when the same query has to run for several inputs.

- First merge them into one query that takes the inputs as a list parameter.
- When independent queries cannot be merged and `db.is_transaction` is false, start them together and await them together, each in its own session and with a bound on how many run at once.
- Await a query inside a `for` loop only as the last resort: when a query needs the result of the one before it, or when the queries belong to one transaction.

Full reference: `dev/guidelines/backend/python.md` §"Several queries of the same shape: one query, then parallel, a loop last".
