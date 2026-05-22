import { useAtomValue } from "jotai";

import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/proposed-change.types";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";

export const useProposedChange = (): ProposedChangeDetail => {
  const proposedChange = useAtomValue(proposedChangedState);
  if (!proposedChange) {
    throw new Error(
      "useProposedChange called before proposedChangedState atom was hydrated. Render must be gated on the loaded proposed change."
    );
  }
  return proposedChange;
};
