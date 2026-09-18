import { parseAsString, parseAsStringLiteral, useQueryStates } from "nuqs";
import { useEffect, useState } from "react";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { useDebounce } from "@/shared/hooks/useDebounce";

const SEARCH_DEBOUNCE_MS = 300;

// A repository's branches never come back as `MERGED` or `DELETING`, so offering either would only
// ever produce an empty result.
export const FILTERABLE_BRANCH_STATUSES = [
  BranchStatus.OPEN,
  BranchStatus.NEED_REBASE,
  BranchStatus.NEED_UPGRADE_REBASE,
  BranchStatus.MERGING,
  BranchStatus.MERGE_FAILED,
] as const;

export type FilterableBranchStatus = (typeof FILTERABLE_BRANCH_STATUSES)[number];

export interface RepositoryBranchFilters {
  name: string;
  status: FilterableBranchStatus | null;
}

export interface UseRepositoryBranchFiltersOptions {
  urlKey: string;
  onFilterChange: () => void;
}

export interface RepositoryBranchFiltersState {
  filters: RepositoryBranchFilters;
  hasFilters: boolean;
  nameInput: string;
  setNameInput: (name: string) => void;
  setStatus: (status: FilterableBranchStatus | null) => void;
}

export function useRepositoryBranchFilters({
  urlKey,
  onFilterChange,
}: UseRepositoryBranchFiltersOptions): RepositoryBranchFiltersState {
  const [params, setParams] = useQueryStates(
    {
      name: parseAsString.withDefault(""),
      status: parseAsStringLiteral(FILTERABLE_BRANCH_STATUSES),
    },
    { urlKeys: { name: `${urlKey}_name`, status: `${urlKey}_status` } }
  );

  const [nameInput, setNameInput] = useState(params.name);
  const [previousName, setPreviousName] = useState(params.name);
  const debouncedName = useDebounce(nameInput, SEARCH_DEBOUNCE_MS);

  // The page reset lives with the write so that no filter can be given its own path around it.
  const setFilters = (next: Partial<RepositoryBranchFilters>) => {
    setParams(next);
    onFilterChange();
  };

  useEffect(() => {
    if (debouncedName === params.name) return;

    setFilters({ name: debouncedName });
  }, [debouncedName]);

  if (params.name !== previousName && nameInput === debouncedName) {
    setPreviousName(params.name);
    setNameInput(params.name);
  }

  return {
    filters: { name: params.name, status: params.status },
    hasFilters: params.name.length > 0 || params.status !== null,
    nameInput,
    setNameInput,
    setStatus: (status) => {
      setFilters({ status });
    },
  };
}
