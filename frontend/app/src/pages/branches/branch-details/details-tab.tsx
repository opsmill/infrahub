import { parseAsInteger, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import { BranchDetails } from "@/entities/branches/ui/branch-details";
import { useBranchDetailsOutlet } from "@/entities/branches/ui/routing/use-branch-details-outlet";

export function Component() {
  const { branch } = useBranchDetailsOutlet();
  const [reposPage, setReposPage] = useQueryState(
    QSP.REPOSITORIES_PAGE,
    parseAsInteger.withDefault(1)
  );
  const [tasksPage, setTasksPage] = useQueryState(QSP.TASKS_PAGE, parseAsInteger.withDefault(1));

  return (
    <BranchDetails
      branchName={branch.name}
      reposPage={reposPage}
      onReposPageChange={setReposPage}
      tasksPage={tasksPage}
      onTasksPageChange={setTasksPage}
    />
  );
}
