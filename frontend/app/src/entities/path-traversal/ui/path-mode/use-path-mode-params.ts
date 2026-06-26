import { parseAsInteger, parseAsNativeArrayOf, parseAsString, useQueryStates } from "nuqs";

export const PATH_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  destination: parseAsString.withDefault(""),
  depth: parseAsInteger.withDefault(5),
  maxPaths: parseAsInteger.withDefault(10),
  kindFilter: parseAsNativeArrayOf(parseAsString).withDefault([]),
  excludedKinds: parseAsNativeArrayOf(parseAsString).withDefault([]),
  selectedPath: parseAsInteger.withDefault(0),
} as const;

export type PathModeParams = {
  source: string;
  destination: string;
  depth: number;
  maxPaths: number;
  kindFilter: string[];
  excludedKinds: string[];
  selectedPath: number;
};

export type PathModeFormValues = {
  sourceId: string;
  destinationId: string;
  maxDepth: number;
  maxPaths: number;
  kindFilter: string[];
  excludedKinds: string[];
};

export function paramsToFormValues(p: PathModeParams): PathModeFormValues {
  return {
    sourceId: p.source,
    destinationId: p.destination,
    maxDepth: p.depth,
    maxPaths: p.maxPaths,
    kindFilter: p.kindFilter,
    excludedKinds: p.excludedKinds,
  };
}

export function formValuesToParams(v: PathModeFormValues): Partial<PathModeParams> {
  return {
    source: v.sourceId,
    destination: v.destinationId,
    depth: v.maxDepth,
    maxPaths: v.maxPaths,
    kindFilter: v.kindFilter,
    excludedKinds: v.excludedKinds,
    selectedPath: 0,
  };
}

export function usePathModeParams() {
  return useQueryStates(PATH_MODE_PARAMS, { history: "push" });
}
