import type { CombinedError } from "@urql/core";
import React from "react";
import { toast } from "react-toastify";

import { ERROR_CODES, parseCatalogueError } from "@/shared/api/errors";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { redirectToLogin } from "@/entities/authentication/domain/use-cases/redirect-to-login";

import type { GraphQLRequestContext } from "./types";

export function hasCatalogueCode(error: CombinedError | undefined, code: string): boolean {
  return (
    error?.graphQLErrors?.some((e) => parseCatalogueError(e.extensions).code === code) ?? false
  );
}

function notifyUser(message: string | undefined, context?: GraphQLRequestContext): void {
  if (!message) return;

  if (context?.processErrorMessage) {
    context.processErrorMessage(message);
    return;
  }

  toast(React.createElement(Alert, { type: ALERT_TYPES.ERROR, message }), {
    toastId: "alert-error",
  });
}

export function handleGraphQLErrors(
  error: CombinedError | undefined,
  context?: GraphQLRequestContext
): void {
  if (!error?.graphQLErrors?.length) return;

  for (const graphQLError of error.graphQLErrors) {
    const parsed = parseCatalogueError(graphQLError.extensions);

    console.error(
      `[GraphQL error]: Code: ${parsed.code}, Message: ${graphQLError.message}, ` +
        `Path: ${graphQLError.path}`
    );

    switch (parsed.code) {
      case ERROR_CODES.TOKEN_EXPIRED:
        redirectToLogin();
        return;

      case ERROR_CODES.AUTHENTICATION_REQUIRED:
        redirectToLogin();
        return;

      case ERROR_CODES.PERMISSION_DENIED:
        // 403s are handled by route-level guards; `continue` so sibling errors still route.
        continue;

      case ERROR_CODES.UNDEFINED_ERROR:
        // Unknown catalogue code: surface it loudly in dev so the gap gets registered.
        if (import.meta.env.DEV) {
          console.error(
            "[catalogue gap] Unmatched error code surfaced as UNDEFINED_ERROR. " +
              "Register it in backend/infrahub/errors/catalogue.py, regenerate " +
              "the schema, and run `pnpm generate:error-bindings`.",
            { message: graphQLError.message, extensions: graphQLError.extensions }
          );
        }
        notifyUser(graphQLError.message, context);
        return;

      default:
        notifyUser(graphQLError.message, context);
        return;
    }
  }
}
