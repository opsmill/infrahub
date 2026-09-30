import { useState } from "react";

import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";

// A refetch on the same query key replaces the data outright, so `keepPreviousData` alone
// cannot stop a poll answering UNAVAILABLE from blanking a list that was already loaded.
export function useLastLoadedCommitPages(pages: RepositoryCommitLog[] | undefined) {
  const [lastLoaded, setLastLoaded] = useState(pages);

  const firstPage = pages?.[0];
  const isColdAnswer = firstPage !== undefined && !isGitStateAvailable(firstPage);

  if (!isColdAnswer && pages !== lastLoaded) {
    setLastLoaded(pages);
  }

  return isColdAnswer && lastLoaded ? lastLoaded : pages;
}
