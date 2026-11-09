import { atom } from "jotai";

import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/model/proposed-change";

export const proposedChangedState = atom<ProposedChangeDetail | null>(null);
