// Hand-written entry point for the catalogue-driven error types. Re-exports
// the generated discriminated union and adds runtime helpers (`isCatalogueError`
// guard + `parseCatalogueError` narrowing parser). Consumers import from this
// barrel — they should never reach into `catalogue.generated.ts` directly.
//
// Regenerate the underlying file with `pnpm generate:error-bindings` when
// the backend catalogue changes; `pnpm check:error-bindings` is wired into
// lint to fail when the committed output drifts from `schema/error-catalogue.json`.
import {
  type CatalogueError,
  ERROR_CODES,
  ERROR_HTTP_STATUS,
  type ErrorCode,
} from "./catalogue.generated";

// biome-ignore lint/performance/noBarrelFile: catalogue's public entry point — single import path for consumers is cheaper than scattering imports across two files.
export {
  type AttributeConstraintViolationData,
  type AttributeInvalidTypeData,
  type AttributeRequiredData,
  type AuthenticationRequiredData,
  type BranchNotFoundData,
  type CatalogueError,
  ERROR_CODES,
  ERROR_HTTP_STATUS,
  type ErrorCode,
  type NodeNotFoundData,
  type PermissionDeniedData,
  type SchemaNotFoundData,
  type TokenExpiredData,
  type UndefinedErrorData,
} from "./catalogue.generated";

const KNOWN_CODES = new Set<string>(Object.values(ERROR_CODES));

// Narrow `extensions` to a known catalogue code. Returns false for:
//   - `null` / `undefined` / non-object inputs
//   - objects whose `code` is missing, not a string, or not in the catalogue
// Callers that need a guaranteed value (with an UNDEFINED_ERROR fallback)
// should use `parseCatalogueError` instead.
export function isCatalogueError(extensions: unknown): extensions is CatalogueError {
  if (extensions === null || typeof extensions !== "object") return false;
  const code = (extensions as { code?: unknown }).code;
  return typeof code === "string" && KNOWN_CODES.has(code);
}

const UNDEFINED_FALLBACK: CatalogueError = {
  code: ERROR_CODES.UNDEFINED_ERROR,
  http_status: ERROR_HTTP_STATUS.UNDEFINED_ERROR,
  data: {},
};

type RawErrorEnvelope = {
  code: ErrorCode;
  http_status?: unknown;
  data?: unknown;
};

/**
 * Parse a raw `extensions` blob from an Apollo `GraphQLError` into a typed
 * `CatalogueError`. Unknown codes and malformed payloads collapse to
 * `UNDEFINED_ERROR` (http_status 500, empty data) so every caller gets a
 * narrowed value — there is no `undefined` return.
 *
 * Runtime trust note: we only validate the envelope shape (`code` is a known
 * catalogue value, `http_status` is a positive number, `data` is an object).
 * The inner `data` payload is NOT re-validated against its per-code schema —
 * the backend contract guarantees a matching payload, and the final
 * `as CatalogueError` coercion reflects that trust. If a callsite needs
 * runtime data validation, layer a Zod parser on top.
 */
export function parseCatalogueError(extensions: unknown): CatalogueError {
  if (!isCatalogueError(extensions)) return UNDEFINED_FALLBACK;

  const { code, http_status: rawHttpStatus, data: rawData } = extensions as RawErrorEnvelope;
  const httpStatusNum = Number(rawHttpStatus);
  const http_status =
    Number.isFinite(httpStatusNum) && httpStatusNum > 0 ? httpStatusNum : ERROR_HTTP_STATUS[code];
  const data = rawData !== null && typeof rawData === "object" ? rawData : {};

  return { code, http_status, data } as CatalogueError;
}
