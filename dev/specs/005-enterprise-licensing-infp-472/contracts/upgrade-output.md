# Contract: license section of `infrahub upgrade`

Printed at the end of `infrahub upgrade` and `infrahub upgrade --check`, through the same console as the rest of the output.

```text
# Today
$ infrahub upgrade --check
...
Run 'infrahub upgrade' to apply all changes.

# After, no license required (Community, or Enterprise without a license service)
... (unchanged, no license section)

# After, quiet mode, no license set
...
License: not set
  Set INFRAHUB_LICENSE_KEY on the servers and task workers.
  From Infrahub 1.13, every user sees an Unlicensed banner without it.

# After, quiet mode with no enforcing release named
  In a future release, every user will see an Unlicensed banner without it.

# After, enforce mode, no license set
License: not set
  Every user sees an Unlicensed banner until INFRAHUB_LICENSE_KEY is set on the servers and task workers.

# After, valid
License: ACME Test Ltd, commercial, ends 2027-09-30

# After, expiring
License: ACME Test Ltd, commercial, expires in 12 days (2027-09-30)

# After, expired
License: expired on 2027-09-30, 4 days ago. Renew it and set the new INFRAHUB_LICENSE_KEY.

# After, not yet valid
License: starts on 2027-10-01. Infrahub runs as unlicensed until then.

# After, invalid
License: could not be verified (bad_signature). Check INFRAHUB_LICENSE_KEY on the servers and task workers.
```

## Rules

- Nothing is printed when the state is `not_required`.
- Dates show the last day covered (`ends_at` minus one second), in UTC.
- When fewer than one whole day has passed since the end (`days_since_expiry` is 0), the count reads "today" instead of "0 days ago", as the About dialog's "expired today".
- The command never prompts because of the license and never changes its exit code because of it.
- An error while building the section is logged and the section is skipped.
- The key itself is never printed.
