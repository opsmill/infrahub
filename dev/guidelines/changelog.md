## Towncrier for changelog

Towncrier is used to manage the changelog which is being published with every release.
Every issue that is being fixed, or new feature that gets implemented should be accompanied by a proper changelog entry.

The changelog message should be a short and user-facing. It should describe what has been fixed or implemented without focusing on the technical aspects of the implementation.

To create a new changelog entry use the following command.
The filename should be in the format `${ISSUE}.{ACTION}.md`:

- ${ISSUE}: the id of the GitHub issue or feature request, if you are not working on an issue or feature request use `+`.
- ${ACTION}: one of added, fixed, housekeeping

```bash
uv run towncrier -c "content of changelog entry" ${ISSUE}.{ACTION}.md
```
