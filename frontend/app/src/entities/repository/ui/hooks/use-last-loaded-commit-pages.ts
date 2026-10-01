import { useState } from "react";

import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";

// A refetch on the same query key replaces the data outright, so a poll answering UNAVAILABLE
// would blank a list that was already loaded.
export function useLastLoadedCommitPages(pages: RepositoryCommitLog[] | undefined) {
  const [lastLoaded, setLastLoaded] = useState<RepositoryCommitLog[]>();

  const firstPage = pages?.[0];
  const isColdAnswer = firstPage !== undefined && !isGitStateAvailable(firstPage);

  if (!isColdAnswer && pages !== lastLoaded) {
    setLastLoaded(pages);
  }

  const isSameLog =
    firstPage !== undefined &&
    lastLoaded?.[0]?.repository_id === firstPage.repository_id &&
    lastLoaded[0].branch_name === firstPage.branch_name;

  return isColdAnswer && isSameLog ? lastLoaded : pages;
}
