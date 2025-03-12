import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { constructPath } from "@/shared/api/rest/fetch";

export const getLink = ({ kind, id, branch }: { kind: string; id: string; branch: string }) => {
  if (kind === PROPOSED_CHANGES_OBJECT) {
    return constructPath(`/proposed-changes/${id}`);
  }

  if (kind === ACCOUNT_OBJECT) {
    return constructPath("/role-management", [
      {
        name: QSP.BRANCH,
        value: branch,
      },
    ]);
  }

  return constructPath(`/objects/${kind}/${id}`, [
    {
      name: QSP.BRANCH,
      value: branch,
    },
  ]);
};
