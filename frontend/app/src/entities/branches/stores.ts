import { atom } from "jotai";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";

export const branchesState = atom<BranchListItem[]>([]);

export const currentBranchAtom = atom<BranchListItem | null>(null);
