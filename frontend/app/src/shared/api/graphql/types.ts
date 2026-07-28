import type { CombinedError } from "@urql/core";

// Kept separate from urql's `OperationContext` so callers don't depend on the transport lib.
export interface GraphQLRequestContext {
  branch?: string | null;
  date?: Date | null;
  processErrorMessage?: (message: string) => void;
}

// Preserved 1:1 from Apollo's `ApolloQueryResult`; callers read either `errors` (array) or
// `error` (single), and `if (errors)` must stay falsy on success, so `errors` is never `[]`.
// `data` is non-optional to keep the many `data.Field` call sites compiling; at runtime it may
// be null on error.
export interface GraphQLResult<TData> {
  data: TData;
  error?: CombinedError;
  errors?: Array<{ message: string }>;
}
