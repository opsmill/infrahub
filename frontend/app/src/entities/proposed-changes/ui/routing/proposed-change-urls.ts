import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";

export type ProposedChangeDetailsTab =
  | "data"
  | "files"
  | "artifacts"
  | "schema"
  | "checks"
  | "tasks";

export function getProposedChangeDetailsUrl(
  proposedChangeId: string,
  tab?: ProposedChangeDetailsTab,
  overrideParams?: overrideQueryParams[]
): string {
  const path = tab
    ? `/proposed-changes/${proposedChangeId}/${tab}`
    : `/proposed-changes/${proposedChangeId}`;
  return constructPath(path, overrideParams);
}
