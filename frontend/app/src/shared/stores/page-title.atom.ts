import { atom } from "jotai";

export interface PageTitleRegistration {
  readonly id: string;
  readonly title: string;
}

export const pageTitleRegistrationsAtom = atom<readonly PageTitleRegistration[]>([]);

export const pageTitleAtom = atom((get) => get(pageTitleRegistrationsAtom).at(-1)?.title ?? null);
