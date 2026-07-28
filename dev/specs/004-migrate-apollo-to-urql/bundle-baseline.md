# Bundle Size: Before / After (SC-001)

Measured by summing the gzipped size of every `dist/assets/*.js` chunk from a
production `pnpm build`, on the same machine.

| Build | Total gzipped JS | JS chunks |
|---|---|---|
| `develop` (Apollo) | 4,574,160 bytes | 386 |
| `migrate-apollo-to-urql-infp-563` (urql) | 4,539,212 bytes | 388 |
| **Delta** | **−34,948 bytes (~−34.1 KB gzipped)** | +2 |

**Result: SC-001 met** — the production bundle shrank. The ~34 KB reduction is
consistent with removing `@apollo/client` (~51.8 KB gz) + `apollo-upload-client`
and adding `@urql/core` (~10.3 KB gz) + `@urql/exchange-auth`; the remainder of
Apollo's footprint overlapped with `graphql`, which is still shipped (used by
`gql.tada`). The small chunk-count increase is code-splitting redistribution,
not new payload.

Method (reproducible):
```bash
# develop baseline built in an isolated git worktree (submodule initialised)
total=0; for f in dist/assets/*.js; do total=$((total + $(gzip -c "$f" | wc -c))); done; echo $total
```
