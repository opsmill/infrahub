// Hand-written mirror of backend/infrahub/errors/catalogue.py. Delete this
// file once US2's generated bindings (tasks T027–T030) land and re-export
// the catalogue from frontend/app/src/shared/api/errors/. Until then, keep
// this file in sync with the backend catalogue — both columns belong to
// the same release.

export const ERROR_CODES = {
  NODE_NOT_FOUND: "NODE_NOT_FOUND",
  AUTHENTICATION_REQUIRED: "AUTHENTICATION_REQUIRED",
  TOKEN_EXPIRED: "TOKEN_EXPIRED",
  PERMISSION_DENIED: "PERMISSION_DENIED",
  ATTRIBUTE_REQUIRED: "ATTRIBUTE_REQUIRED",
  ATTRIBUTE_INVALID_TYPE: "ATTRIBUTE_INVALID_TYPE",
  ATTRIBUTE_CONSTRAINT_VIOLATION: "ATTRIBUTE_CONSTRAINT_VIOLATION",
  BRANCH_NOT_FOUND: "BRANCH_NOT_FOUND",
  SCHEMA_NOT_FOUND: "SCHEMA_NOT_FOUND",
  UNDEFINED_ERROR: "UNDEFINED_ERROR",
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

// Payload shapes — one per code. Match backend/infrahub/errors/payloads.py.
type NodeNotFoundData = { node_kind: string; identifier: string };
type AuthenticationRequiredData = Record<string, never>;
type TokenExpiredData = { expired_at: string | null };
type PermissionDeniedData = {
  action: string | null;
  resource_kind: string | null;
};
type AttributeRequiredData = { node_kind: string; field_name: string };
type AttributeInvalidTypeData = {
  node_kind: string;
  field_name: string;
  expected_type: string;
  received_type: string;
};
type AttributeConstraintViolationData = {
  node_kind: string;
  field_name: string;
  constraint: string;
  detail: string | null;
};
type BranchNotFoundData = { branch_name: string };
type SchemaNotFoundData = { kind: string };
type UndefinedErrorData = Record<string, never>;

// Discriminated union — `code` narrows `data` automatically.
export type GraphQLErrorExtensions =
  | { code: typeof ERROR_CODES.NODE_NOT_FOUND; http_status: number; data: NodeNotFoundData }
  | {
      code: typeof ERROR_CODES.AUTHENTICATION_REQUIRED;
      http_status: number;
      data: AuthenticationRequiredData;
    }
  | { code: typeof ERROR_CODES.TOKEN_EXPIRED; http_status: number; data: TokenExpiredData }
  | {
      code: typeof ERROR_CODES.PERMISSION_DENIED;
      http_status: number;
      data: PermissionDeniedData;
    }
  | {
      code: typeof ERROR_CODES.ATTRIBUTE_REQUIRED;
      http_status: number;
      data: AttributeRequiredData;
    }
  | {
      code: typeof ERROR_CODES.ATTRIBUTE_INVALID_TYPE;
      http_status: number;
      data: AttributeInvalidTypeData;
    }
  | {
      code: typeof ERROR_CODES.ATTRIBUTE_CONSTRAINT_VIOLATION;
      http_status: number;
      data: AttributeConstraintViolationData;
    }
  | { code: typeof ERROR_CODES.BRANCH_NOT_FOUND; http_status: number; data: BranchNotFoundData }
  | { code: typeof ERROR_CODES.SCHEMA_NOT_FOUND; http_status: number; data: SchemaNotFoundData }
  | {
      code: typeof ERROR_CODES.UNDEFINED_ERROR;
      http_status: number;
      data: UndefinedErrorData;
    };

const KNOWN_CODES = new Set<string>(Object.values(ERROR_CODES));

const UNDEFINED_FALLBACK: GraphQLErrorExtensions = {
  code: ERROR_CODES.UNDEFINED_ERROR,
  http_status: 500,
  data: {},
};

/**
 * Parse the raw `extensions` blob from an Apollo `GraphQLError` into a
 * discriminated union. Falls back to `UNDEFINED_ERROR` (http_status 500,
 * empty data) when the payload is missing or carries a code the frontend
 * does not know about, so every caller gets a typed value.
 */
export function parseErrorExtensions(extensions: unknown): GraphQLErrorExtensions {
  if (extensions === null || typeof extensions !== "object") {
    return UNDEFINED_FALLBACK;
  }

  const record = extensions as Record<string, unknown>;
  const rawCode = record.code;

  if (typeof rawCode !== "string" || !KNOWN_CODES.has(rawCode)) {
    return UNDEFINED_FALLBACK;
  }

  const code = rawCode as ErrorCode;
  const httpStatus = Number(record.http_status);
  const data =
    record.data !== null && typeof record.data === "object" ? (record.data as object) : {};

  return {
    code,
    http_status: Number.isFinite(httpStatus) && httpStatus > 0 ? httpStatus : 500,
    // Cast is safe: the discriminated union is gated by `code`, and we do
    // not validate the inner shape at runtime by design (see spec
    // §"Parsing rules" — narrowing is for ergonomics, not runtime trust).
    data: data as never,
  } as GraphQLErrorExtensions;
}
