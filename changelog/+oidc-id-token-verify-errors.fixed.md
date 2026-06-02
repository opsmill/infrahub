A failed OIDC `id_token` verification — invalid signature, audience, issuer, or an unresolvable signing key — now returns an authorization error (HTTP 401) instead of an unhandled server error.
