import { atom } from "jotai";

/**
 * Atom to share the search result count from SearchNodes to SearchAnywhereFooter,
 * avoiding a duplicate useGetSearchAnywhere() hook call in the footer.
 */
export const searchResultCountAtom = atom<number>(0);
