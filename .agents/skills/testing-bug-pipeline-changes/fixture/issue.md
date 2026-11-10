_This issue tests the bug pipeline in this sandbox. The bug exists only in the sandbox copy of the code. Safe to close after the run._

### Component

API Server / GraphQL

### Infrahub version

The sandbox `stable` branch

### Current Behavior

`count_pages` in `backend/infrahub/sandbox_pagination.py` returns one page too few when the number of items is not a multiple of the page size. The items on the last, partly filled page are never counted:

```python
from infrahub.sandbox_pagination import count_pages

count_pages(21, 10)  # returns 2
count_pages(5, 10)   # returns 0
```

### Expected Behavior

`count_pages` returns the number of pages needed to list every item:

- `count_pages(21, 10)` returns 3.
- `count_pages(5, 10)` returns 1.
- `count_pages(20, 10)` returns 2, as it does today.
- `count_pages(0, 10)` returns 0, as it does today.

### Steps to Reproduce

1. Run `uv run python -c "from infrahub.sandbox_pagination import count_pages; print(count_pages(21, 10))"`.
2. The output is `2`, but 21 items at 10 per page need 3 pages.

### Additional Information

The function needs no database, so a unit test can reproduce the bug.
