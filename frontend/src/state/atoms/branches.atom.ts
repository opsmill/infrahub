import { atom } from "jotai";
import { Branch } from "../../generated/graphql";

export const branchesState = atom<Branch[]>([]);
