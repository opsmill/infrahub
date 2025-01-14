import { Branch } from "@/shared/api/graphql/generated/graphql";
import { atom } from "jotai";

export const branchesState = atom<Branch[]>([]);

export const currentBranchAtom = atom<Branch | null>(null);
