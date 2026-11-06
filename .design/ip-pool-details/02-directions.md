# Directions

The four directions come from the prototype commit `8827d389b5` on `bab-proto-ip-pool-design` (route `/proto/ip-pool-defaults`, picker `?v=1..4`, data `?data=1..3`). They share the header, the resource prefix list and the allocated table, and differ only in the one line under the title that names the namespace and the defaults. That line is where the number pool's "Allocates to X attribute y" sentence does not transfer to IP pools, which the ticket lists as an open issue. All four were rendered with a long pool name, a long namespace name, unset defaults, an IPv6 resource prefix and an empty resource prefix.

## 1. Dots (`v=1`)

Namespace and every default in one wrapping row, each entry separated by a middle dot: "In namespace default · Prefix kind defaults to IpamIPPrefix · Prefix length defaults to /31 · Member type defaults to Address". Bets on every entry reading the same way, so an unset default ("Prefix length has no default") sits next to a set one without a different shape. Costs one more line when the row wraps on a narrow window. Suits an engineer who scans the header once.

## 2. Divider (`v=2`)

Namespace first, a vertical rule, then the defaults joined by dots. Bets on the namespace being a different kind of fact from the defaults. Costs a second separator style in one line. Suits a pool whose namespace matters more than its defaults.

## 3. Chained (`v=3`)

Namespace, a vertical rule, then one sentence: "Prefix kind defaults to IpamIPPrefix, prefix length to /31, member type to Address". Bets on reading as prose. Costs clarity when a default is unset in the middle of the sentence, where "prefix length has no default" breaks the chain and the "to" shorthand no longer applies. Suits pools whose defaults are all set.

## 4. No wrap (`v=4`)

One line that never wraps: the namespace truncates at a fixed width and the defaults truncate at the end. Bets on a fixed header height. Costs the end of the line on a narrow window, where the member type disappears with no way to read it. Suits wide screens only.

## Decision

Paul Leménager picked Dots on 2026-11-04. Divider and Chained were rejected because they add a second separator or break on an unset default; No wrap because it hides a default instead of wrapping.
