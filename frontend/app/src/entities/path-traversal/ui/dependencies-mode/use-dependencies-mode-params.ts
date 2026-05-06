import { parseAsInteger, parseAsNativeArrayOf, parseAsString, useQueryStates } from "nuqs";

export const DEPENDENCIES_MODE_PARAMS = {
  source: parseAsString.withDefault(""),
  targetKinds: parseAsNativeArrayOf(parseAsString).withDefault([]),
  depth: parseAsInteger.withDefault(5),
  selectedIndex: parseAsInteger.withDefault(0),
} as const;

export type DependenciesModeParams = {
  source: string;
  targetKinds: string[];
  depth: number;
  selectedIndex: number;
};

export type DependenciesModeFormValues = {
  sourceId: string;
  targetKinds: string[];
  maxDepth: number;
};

export function paramsToFormValues(p: DependenciesModeParams): DependenciesModeFormValues {
  return {
    sourceId: p.source,
    targetKinds: p.targetKinds,
    maxDepth: p.depth,
  };
}

export function formValuesToParams(v: DependenciesModeFormValues): Partial<DependenciesModeParams> {
  return {
    source: v.sourceId,
    targetKinds: v.targetKinds,
    depth: v.maxDepth,
    selectedIndex: 0,
  };
}

export function useDependenciesModeParams() {
  return useQueryStates(DEPENDENCIES_MODE_PARAMS, { history: "push" });
}
