# Contract: license section of `infrahub upgrade`

Printed through the same console as the rest of the output. In `infrahub upgrade --check` it comes after the branch report and before the closing "Run 'infrahub upgrade' to apply all changes." line. In `infrahub upgrade` it comes last, after "Upgrade complete"; an upgrade that stops on a failed migration prints no license section.

```text
# Today
$ infrahub upgrade --check
...
Run 'infrahub upgrade' to apply all changes.

# After, no license required (Community, or Enterprise without a license service)
... (unchanged, no license section)

# After, quiet mode, no license set
$ infrahub upgrade --check
...
License: not set
  Set INFRAHUB_LICENSE_KEY on the servers and task workers.
  From Infrahub 1.13, every user sees an Unlicensed banner without it.

Run 'infrahub upgrade' to apply all changes.

# After, quiet mode with no enforcing release named
  In a future release, every user will see an Unlicensed banner without it.

# After, enforce mode, no license set
License: not set
  Every user sees an Unlicensed banner until INFRAHUB_LICENSE_KEY is set on the servers and task workers.

# After, valid
License: ACME Test Ltd, commercial, ends 2027-09-30

# After, expiring
License: ACME Test Ltd, commercial, expires in 12 days (2027-09-30)

# After, expired, enforce mode
License: expired on 2027-09-30, 4 days ago. Renew it and set the new INFRAHUB_LICENSE_KEY.

# After, expired, quiet mode
License: expired on 2027-09-30, 4 days ago. Renew it and set the new INFRAHUB_LICENSE_KEY.
  From Infrahub 1.13, every user sees a license banner until this is resolved.

# After, not yet valid, enforce mode
License: starts on 2027-10-01. Infrahub runs as unlicensed until then.

# After, not yet valid, quiet mode with no enforcing release named
License: starts on 2027-10-01. Infrahub runs as unlicensed until then.
  In a future release, every user will see a license banner until this is resolved.

# After, invalid, enforce mode
License: could not be verified (bad_signature). Check INFRAHUB_LICENSE_KEY on the servers and task workers.

# After, invalid, quiet mode
License: could not be verified (bad_signature). Check INFRAHUB_LICENSE_KEY on the servers and task workers.
  From Infrahub 1.13, every user sees a license banner until this is resolved.

# After, invalid because of an internal error, either mode
License: could not be determined because of an internal error. Check the server logs.
```

## Rules

- Nothing is printed when the state is `not_required`.
- The release note ("From Infrahub <release>, every user sees ..." or, with no enforcing release named, "In a future release, every user will see ...") is added exactly when `banner.shown_to_all_users_when_enforced` of [api-info.md](api-info.md) is true: quiet mode, and a state of `unlicensed`, `expired`, `not_yet_valid`, or `invalid` with any reason but `internal_error`. It is never added for `valid`, `expiring` or `internal_error`. The note names an "Unlicensed banner" for `unlicensed` and "a license banner" for the other states.
- In enforce mode, `unlicensed` says that every user sees the banner; the other states print their state line only.
- `invalid` with `internal_error` is a defect in Infrahub, not in the customer's license, so it points at the server logs and gives no key advice. The other reasons name the reason code and point at the key.
- The type reads `evaluation` for an evaluation license and `commercial` otherwise, including for a type this release does not know.
- An end date shows the last day covered (`ends_at` minus one microsecond, the smallest unit a `License` datetime keeps, so an end at `00:00:00.500000Z` still shows that day) and a start date the first, both in UTC.
- When fewer than one whole day has passed since the end (`days_since_expiry` is 0), the count reads "today" instead of "0 days ago", as the About dialog's "expired today". A count of one reads "1 day".
- The command never prompts because of the license and never changes its exit code because of it.
- An error while building the section is logged and the section is skipped.
- The key itself is never printed.
