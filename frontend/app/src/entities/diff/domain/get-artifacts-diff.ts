import type { components } from "@/shared/api/rest/types.generated";

import {
  type GetArtifactsDiffFromApiParams,
  getArtifactsDiffFromApi,
} from "@/entities/diff/api/get-artifacts-diff-from-api";

type BranchDiffArtifact = components["schemas"]["BranchDiffArtifact"];

export type ArtifactDiff = BranchDiffArtifact;

export type GetArtifactsDiffParams = GetArtifactsDiffFromApiParams;

const ACTION_PRIORITY: Record<string, number> = {
  added: 1,
  updated: 2,
  removed: 3,
  unchanged: 4,
};

export async function getArtifactsDiff({
  branch,
}: GetArtifactsDiffParams): Promise<ArtifactDiff[]> {
  const data = await getArtifactsDiffFromApi({ branch });

  const artifacts = Object.values(data ?? {});

  return artifacts.sort((a, b) => {
    const actionDiff = (ACTION_PRIORITY[a.action] ?? 99) - (ACTION_PRIORITY[b.action] ?? 99);
    if (actionDiff !== 0) return actionDiff;

    return (a.display_label ?? "").localeCompare(b.display_label ?? "", undefined, {
      sensitivity: "base",
    });
  });
}
