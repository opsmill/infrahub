import type { CombinedError } from "@urql/core";

export interface GraphQLRequestContext {
  branch?: string | null;
  date?: Date | null;
  processErrorMessage?: (message: string) => void;
  /** Queries only: returns integers beyond `Number.MAX_SAFE_INTEGER` as strings, because parsing them as numbers rounds them. */
  keepLargeIntegersExact?: boolean;
}

export interface GraphQLResult<TData> {
  data: TData;
  error?: CombinedError;
  errors?: Array<{ message: string }>;
}
