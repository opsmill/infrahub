import { atomWithStorage } from "jotai/utils";

export interface ParallelQueryConfig {
  enabled: boolean;
  pageSize: number;
  maxConcurrent: number;
  delayMs: number;
}

const defaultConfig: ParallelQueryConfig = {
  enabled: false,
  pageSize: 500,
  maxConcurrent: 5,
  delayMs: 0,
};

// Read on init so the transport, which reads outside React, never sees the default before a saved value.
export const parallelQueryConfigAtom = atomWithStorage<ParallelQueryConfig>(
  "graphiql-parallel-mode",
  defaultConfig,
  undefined,
  { getOnInit: true }
);
