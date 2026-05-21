import { atom } from "jotai";

import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/proposed-change.types";

export const proposedChangedState = atom<ProposedChangeDetail | null>(null);
