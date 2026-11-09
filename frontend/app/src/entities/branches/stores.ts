import { atom } from "jotai";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";

export const branchesState = atom<BranchListItem[]>([]);
