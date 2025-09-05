import { atom } from "jotai";

import { Branch } from "@/shared/api/graphql/generated/graphql";

export const branchesState = atom<Branch[]>([]);

export const currentBranchAtom = atom<Branch | null>(null);
