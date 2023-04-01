import { atom } from "jotai";

export const timeState = atom<Date | null | undefined>(undefined);
