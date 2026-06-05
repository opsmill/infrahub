import { parseAsInteger, parseAsNativeArrayOf, parseAsString, useQueryStates } from "nuqs";

export const DEPENDENCIES_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  targetKinds: parseAsNativeArrayOf(parseAsString).withDefault([]),
  depth: parseAsInteger.withDefault(5),
  maxResults: parseAsInteger.withDefault(50),
  maxPaths: parseAsInteger.withDefault(500),
  selectedIndex: parseAsInteger.withDefault(0),
} as const;

export type DependenciesModeParams = {
  source: string;
  targetKinds: string[];
  depth: number;
  maxResults: number;
  maxPaths: number;
  selectedIndex: number;
};

export type DependenciesModeFormValues = {
  sourceId: string;
  targetKinds: string[];
  maxDepth: number;
  maxResults: number;
  maxPaths: number;
};

export function paramsToFormValues(p: DependenciesModeParams): DependenciesModeFormValues {
  return {
    sourceId: p.source,
    targetKinds: p.targetKinds,
    maxDepth: p.depth,
    maxResults: p.maxResults,
    maxPaths: p.maxPaths,
  };
}

export function formValuesToParams(v: DependenciesModeFormValues): Partial<DependenciesModeParams> {
  return {
    source: v.sourceId,
    targetKinds: v.targetKinds,
    depth: v.maxDepth,
    maxResults: v.maxResults,
    maxPaths: v.maxPaths,
    selectedIndex: 0,
  };
}

export function useDependenciesModeParams() {
  return useQueryStates(DEPENDENCIES_MODE_PARAMS, { history: "push" });
}
