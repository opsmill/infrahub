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
