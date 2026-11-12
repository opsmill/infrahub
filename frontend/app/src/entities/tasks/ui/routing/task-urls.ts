import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import { getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";

export function getTaskDetailsUrl(taskId: string): string {
  return constructPath(`/tasks/${taskId}`);
}

export function getTasksPageUrl(
  branchName: string,
  filters: { name: string; value: string }[]
): string {
  return constructPath("/tasks", [
    getBranchQsp(branchName),
    {
      name: QSP.FILTER,
      value: JSON.stringify([{ name: "branch__value", value: branchName }, ...filters]),
    },
  ]);
}
