import { createContext, type ReactNode, useContext, useState } from "react";

export interface ParallelQueryConfig {
  enabled: boolean;
  pageSize: number; // Default: 500
  maxConcurrent: number; // Default: 5
  delayMs: number; // Default: 0 (disabled) - delay between queries
}

interface ParallelQueryContextType {
  config: ParallelQueryConfig;
  setConfig: (config: Partial<ParallelQueryConfig>) => void;
  toggleEnabled: () => void;
}

const defaultConfig: ParallelQueryConfig = {
  enabled: false,
  pageSize: 500,
  maxConcurrent: 5,
  delayMs: 0,
};

const ParallelQueryContext = createContext<ParallelQueryContextType | null>(null);

export function ParallelQueryProvider({ children }: { children: ReactNode }) {
  const [config, setConfigState] = useState<ParallelQueryConfig>(defaultConfig);

  const setConfig = (partial: Partial<ParallelQueryConfig>) => {
    setConfigState((prev) => ({ ...prev, ...partial }));
  };

  const toggleEnabled = () => {
    setConfigState((prev) => ({ ...prev, enabled: !prev.enabled }));
  };

  return (
    <ParallelQueryContext.Provider value={{ config, setConfig, toggleEnabled }}>
      {children}
    </ParallelQueryContext.Provider>
  );
}

export function useParallelQueryMode() {
  const context = useContext(ParallelQueryContext);
  if (!context) {
    throw new Error("useParallelQueryMode must be used within ParallelQueryProvider");
  }
  return context;
}
