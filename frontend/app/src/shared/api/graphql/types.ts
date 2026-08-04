import type { CombinedError } from "@urql/core";

export interface GraphQLRequestContext {
  branch?: string | null;
  date?: Date | null;
  processErrorMessage?: (message: string) => void;
  signal?: AbortSignal;
}

export interface GraphQLResult<TData> {
  data: TData;
  error?: CombinedError;
  errors?: Array<{ message: string }>;
}
