import { QSP } from "@/shared/config/qsp";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";

// REST error envelope item. The REST and GraphQL envelopes carry different
// `code` shapes and must not be conflated:
//
//   REST     extensions.code = number  (HTTP status, e.g. 401)
//   GraphQL  extensions.code = string  (catalogue identifier, e.g. "TOKEN_EXPIRED")
//            extensions.http_status = number (the HTTP status lives here instead)
//
// The GraphQL counterpart lives at @/shared/api/errors (`CatalogueError`).
// If REST endpoints ever migrate to the catalogue, this type becomes a
// discriminated union — until then, keep the two shapes distinct.
export type RestErrorItem = { message: string; extensions: { code: number } };

// Typed wrapper around a REST envelope that carries `errors`. `status`
// is the HTTP status — usually non-2xx, but may also be 2xx for SSO-style
// "200 with errors" responses (see pages/auth-callback.tsx), so callers
// must not assume `status >= 400`.
export class FetchError extends Error {
  status: number;
  errors?: RestErrorItem[];

  constructor(status: number, errors?: RestErrorItem[]) {
    super(`Request failed with status ${status}`);
    this.name = "FetchError";
    this.status = status;
    this.errors = errors;
  }
}

export const fetchUrl = async (url: string, payload?: RequestInit) => {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const newPayload = {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(localToken ? { authorization: `Bearer ${localToken}` } : {}),
      ...payload?.headers,
    },
    method: payload?.method ?? "GET",
    ...(payload?.method === "POST"
      ? {
          body: payload?.body ?? "",
        }
      : {}),
  };

  const rawResponse = await fetch(url, newPayload);

  if (!rawResponse.ok) {
    // Try to surface the REST error envelope ({errors: [...]}) so callers
    // (e.g. SSO auth-callback → /login) can render server-provided messages.
    // Falls back to a bare FetchError when the body is missing or not JSON.
    let errors: RestErrorItem[] | undefined;
    try {
      const body = (await rawResponse.json()) as unknown;
      if (
        body &&
        typeof body === "object" &&
        Array.isArray((body as { errors?: unknown }).errors)
      ) {
        errors = (body as { errors: RestErrorItem[] }).errors;
      }
    } catch {
      // Body wasn't JSON — leave errors undefined.
    }
    throw new FetchError(rawResponse.status, errors);
  }

  return rawResponse.json();
};

const QSP_TO_INCLUDE = [QSP.BRANCH, QSP.DATETIME];

export type overrideQueryParams = {
  name: string;
  value?: string | null;
  exclude?: boolean;
};

// Construct link with path that contains all QSP
export const constructPath = (
  path: string,
  overrideParams?: overrideQueryParams[],
  preserveQspLib: string[] = []
) => {
  const currentURLSearchParams = getCurrentQsp();
  const newURLSearchParams = new URLSearchParams();

  // Remove some QSP if not needed to be forwarded
  [...QSP_TO_INCLUDE, ...preserveQspLib].forEach((qsp) => {
    const paramValue = currentURLSearchParams.get(qsp);
    if (paramValue) newURLSearchParams.set(qsp, paramValue);
  });

  overrideParams?.forEach(({ name, value, exclude }) => {
    if (exclude) {
      newURLSearchParams.delete(name);
    } else if (value) {
      newURLSearchParams.set(name, value);
    }
  });

  // Prevent having a trailing '?'
  if (!newURLSearchParams.toString()) return path;

  if (path.includes("?")) {
    return `${path}&${newURLSearchParams.toString()}`;
  }

  return `${path}?${newURLSearchParams.toString()}`;
};

export const getCurrentQsp = () => new URL(window.location.href).searchParams;
