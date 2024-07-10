import { atom } from "jotai";

export interface iStateAtom {
  isReady?: boolean;
}

export const stateAtom = atom<iStateAtom>({});
