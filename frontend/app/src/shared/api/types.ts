import type { UseMutationOptions } from "@tanstack/react-query";

export type BranchContextParams = {
  branchName: string;
};

export interface ContextParams extends BranchContextParams {
  atDate?: Date | null;
}

export type PaginationParams = {
  limit?: number;
  offset?: number;
};

export type QueryConfig<T extends (...args: any[]) => any> = Omit<
  ReturnType<T>,
  "queryKey" | "queryFn"
>;

export type InfiniteQueryConfig<T extends (...args: any[]) => any> = Omit<
  ReturnType<T>,
  "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
>;

export type MutationConfig<MutationFnType extends (...args: any) => Promise<any>> =
  UseMutationOptions<
    Awaited<ReturnType<MutationFnType>>,
    Error,
    Omit<Parameters<MutationFnType>[0], keyof ContextParams>
  >;
