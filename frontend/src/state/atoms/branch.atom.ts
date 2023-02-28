import { atom } from "jotai";
import { Branch } from "../../generated/graphql";

export const branchState = atom<Branch | null>(null);
