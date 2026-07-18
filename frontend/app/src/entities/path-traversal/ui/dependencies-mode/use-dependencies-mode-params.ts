import {
  parseAsBoolean,
  parseAsInteger,
  parseAsNativeArrayOf,
  parseAsString,
  useQueryStates,
} from "nuqs";

export const DEPENDENCIES_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  targetKinds: parseAsNativeArrayOf(parseAsString).withDefault([]),
  depth: parseAsInteger.withDefault(5),
  maxResults: parseAsInteger.withDefault(50),
  maxPaths: parseAsInteger.withDefault(500),
  shortestPathsOnly: parseAsBoolean.withDefault(true),
  selectedIndex: parseAsInteger.withDefault(0),
} as const;

export type DependenciesModeParams = {
  source: string;
  targetKinds: string[];
  depth: number;
  maxResults: number;
  maxPaths: number;
  shortestPathsOnly: boolean;
  selectedIndex: number;
};

export type DependenciesModeFormValues = {
  sourceId: string;
  targetKinds: string[];
  maxDepth: number;
  maxResults: number;
  maxPaths: number;
  shortestPathsOnly: boolean;
};

export function paramsToFormValues(p: DependenciesModeParams): DependenciesModeFormValues {
  return {
    sourceId: p.source,
    targetKinds: p.targetKinds,
    maxDepth: p.depth,
    maxResults: p.maxResults,
    maxPaths: p.maxPaths,
    shortestPathsOnly: p.shortestPathsOnly,
  };
}

export function formValuesToParams(v: DependenciesModeFormValues): Partial<DependenciesModeParams> {
  return {
    source: v.sourceId,
    targetKinds: v.targetKinds,
    depth: v.maxDepth,
    maxResults: v.maxResults,
    maxPaths: v.maxPaths,
    shortestPathsOnly: v.shortestPathsOnly,
    selectedIndex: 0,
  };
}

export function useDependenciesModeParams() {
  return useQueryStates(DEPENDENCIES_MODE_PARAMS, { history: "push" });
}
