// AUTO-GENERATED — DO NOT EDIT.
// Source: schema/error-catalogue.json
// Catalogue version: 1
// Regenerate with: pnpm generate:error-bindings

export interface AttributeConstraintViolationData {
node_kind: string
field_name: string
constraint: string
detail?: (string | null)
}

export interface AttributeInvalidTypeData {
node_kind: string
field_name: string
expected_type: string
received_type: string
}

export interface AttributeRequiredData {
node_kind: string
field_name: string
}

export interface AuthenticationRequiredData {

}

export interface BranchNotFoundData {
branch_name: string
}

export interface NodeNotFoundData {
node_kind: string
identifier: string
}

export interface PermissionDeniedData {
action?: (string | null)
resource_kind?: (string | null)
}

export interface SchemaNotFoundData {
kind: string
}

export interface TokenExpiredData {
expired_at?: (string | null)
}

export interface UndefinedErrorData {

}

export const ERROR_CODES = {
  ATTRIBUTE_CONSTRAINT_VIOLATION: "ATTRIBUTE_CONSTRAINT_VIOLATION",
  ATTRIBUTE_INVALID_TYPE: "ATTRIBUTE_INVALID_TYPE",
  ATTRIBUTE_REQUIRED: "ATTRIBUTE_REQUIRED",
  AUTHENTICATION_REQUIRED: "AUTHENTICATION_REQUIRED",
  BRANCH_NOT_FOUND: "BRANCH_NOT_FOUND",
  NODE_NOT_FOUND: "NODE_NOT_FOUND",
  PERMISSION_DENIED: "PERMISSION_DENIED",
  SCHEMA_NOT_FOUND: "SCHEMA_NOT_FOUND",
  TOKEN_EXPIRED: "TOKEN_EXPIRED",
  UNDEFINED_ERROR: "UNDEFINED_ERROR",
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

// Default `http_status` per code, as declared by the backend catalogue.
// The runtime envelope still carries `http_status` so consumers can prefer
// that; this lookup is for callers that need the status without a payload.
export const ERROR_HTTP_STATUS: Record<ErrorCode, number> = {
  ATTRIBUTE_CONSTRAINT_VIOLATION: 422,
  ATTRIBUTE_INVALID_TYPE: 422,
  ATTRIBUTE_REQUIRED: 422,
  AUTHENTICATION_REQUIRED: 401,
  BRANCH_NOT_FOUND: 400,
  NODE_NOT_FOUND: 404,
  PERMISSION_DENIED: 403,
  SCHEMA_NOT_FOUND: 422,
  TOKEN_EXPIRED: 401,
  UNDEFINED_ERROR: 500,
};

// Discriminated union over every catalogue code. Narrowing on `code`
// gives full type-safety for `data` at the call site.
export type CatalogueError =
  | { code: typeof ERROR_CODES.ATTRIBUTE_CONSTRAINT_VIOLATION; http_status: number; data: AttributeConstraintViolationData }
  | { code: typeof ERROR_CODES.ATTRIBUTE_INVALID_TYPE; http_status: number; data: AttributeInvalidTypeData }
  | { code: typeof ERROR_CODES.ATTRIBUTE_REQUIRED; http_status: number; data: AttributeRequiredData }
  | { code: typeof ERROR_CODES.AUTHENTICATION_REQUIRED; http_status: number; data: AuthenticationRequiredData }
  | { code: typeof ERROR_CODES.BRANCH_NOT_FOUND; http_status: number; data: BranchNotFoundData }
  | { code: typeof ERROR_CODES.NODE_NOT_FOUND; http_status: number; data: NodeNotFoundData }
  | { code: typeof ERROR_CODES.PERMISSION_DENIED; http_status: number; data: PermissionDeniedData }
  | { code: typeof ERROR_CODES.SCHEMA_NOT_FOUND; http_status: number; data: SchemaNotFoundData }
  | { code: typeof ERROR_CODES.TOKEN_EXPIRED; http_status: number; data: TokenExpiredData }
  | { code: typeof ERROR_CODES.UNDEFINED_ERROR; http_status: number; data: UndefinedErrorData }
  ;
