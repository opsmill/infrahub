# Contract: license banner and About dialog rows

## Banner visibility

The banner renders for a signed-in user when the license object's `banner.audience` is:

- `all_users`; or
- `super_admins` and the user holds the super-admin global permission.

It renders nothing when the viewer is not signed in, when the audience is `none`, when the license object is missing or `null`, or when the app-info request failed. The info endpoint sends `license: null` to anonymous visitors, so they never see the banner. For the `super_admins` audience it also renders nothing until the super-admin permission check has answered, so a regular user never sees a super-admin banner flash.

The server sends the `super_admins` audience, dismissible, for `invalid` with `internal_error` in both modes, so an internal error in Infrahub never shows a banner to every user.

## Dismissal

- Offered only when `banner.dismissible` is true.
- Stored in `sessionStorage` under a key built from the license ID (or `none`) and the state.
- A different license ID or state shows the banner again.

## Text per state

| State | Text | Extra |
| --- | --- | --- |
| `unlicensed` | Infrahub Enterprise is running without a license. Ask your Infrahub administrator for your organization's license, or contact sales. | Deployment ID with a copy action |
| `invalid` | The installed license could not be verified. | Super-admins: the reason explanation (table below) |
| `not_yet_valid` | The installed license starts on {start date}. | |
| `expired` | Your Infrahub Enterprise license expired on {end date}. Contact sales to renew. | |
| `expiring` | Your license expires in {N} days, on {end date}. | |

When `banner.shown_to_all_users_when_enforced` is true, the banner adds: "From Infrahub {enforcing release}, this is shown to all users." When `enforcing_release` is null: "In a future release, this will be shown to all users." The server sets the field (see [api-info.md](api-info.md)); the UI does not derive it from the state or the mode.

### Reason explanations for `invalid` (super-admins only)

New copy, not yet signed off by product.

| Reason | Text |
| --- | --- |
| `malformed` | The license key is not a well-formed license. Check INFRAHUB_LICENSE_KEY on the servers and task workers. |
| `bad_signature` | The license signature does not match its content. Check INFRAHUB_LICENSE_KEY on the servers and task workers. |
| `unknown_key` | The license is signed with a key this release does not recognize. Check INFRAHUB_LICENSE_KEY on the servers and task workers. |
| `wrong_issuer` | The license comes from an issuer this release does not accept. Check INFRAHUB_LICENSE_KEY on the servers and task workers. |
| `wrong_product` | The license is for a different product. Check INFRAHUB_LICENSE_KEY on the servers and task workers. |
| `internal_error` | The license state could not be determined because of an internal error. Check the server logs. |

`internal_error` means Infrahub failed, not the customer's license, so it does not point at the key.

The contact-sales link target is an open question (design Q2) and ships with the first licensing release; this feature renders the text without a link.

## Refresh

The app-info query refetches at least every hour and every time the window regains focus, even when its data is still fresh.

## About dialog rows

Shown to every signed-in user when the license object carries a license:

| Row | Value |
| --- | --- |
| License | `{customer name}` |
| Type | `Commercial`, or `Evaluation license, N days left` |
| Product tier | `{product tier}` |
| Support tier | `{support tier}` |
| Ends | `{end date}` (`{N} days left`, `expired {N} days ago`, or `expired today` when fewer than one whole day has passed since the end) |

When the state is `unlicensed` or `invalid`, a single "License" row shows "Not installed" or "Could not be verified". When the state is `not_required`, no license row is added (the About dialog is unchanged).

A count of one reads `1 day`. No license row is added when the license object is missing or `null`, or when the viewer is not signed in. Anonymous visitors can open the About dialog when anonymous access is allowed; the info endpoint sends them `license: null`.
