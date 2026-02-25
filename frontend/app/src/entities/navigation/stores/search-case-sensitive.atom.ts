import { atomWithStorage } from "jotai/utils";

/**
 * Atom to store the case-sensitive toggle state for search anywhere.
 * Persists in localStorage across page refreshes.
 * Default: false (case-insensitive search)
 */
export const searchCaseSensitiveAtom = atomWithStorage<boolean>("search-case-sensitive", false);
