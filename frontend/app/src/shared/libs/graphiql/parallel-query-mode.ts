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

const STORAGE_KEY = "graphiql-parallel-mode";

export function getParallelQueryConfig(): ParallelQueryConfig {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : defaultConfig;
  } catch {
    return defaultConfig;
  }
}

export function setParallelQueryConfig(partial: Partial<ParallelQueryConfig>): ParallelQueryConfig {
  const current = getParallelQueryConfig();
  const next = { ...current, ...partial };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}
