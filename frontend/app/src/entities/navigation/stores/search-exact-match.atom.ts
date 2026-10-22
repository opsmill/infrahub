import { atomWithStorage } from "jotai/utils";

export const searchExactMatchAtom = atomWithStorage<boolean>("search-exact-match", false);
