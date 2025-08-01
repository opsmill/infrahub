import { createContext, use } from "react";

export interface PcActionsContextType {
  setDraft: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };
  close: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };
  merge: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };
  approve: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };
  reject: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };
}

export const PcActionsContext = createContext<PcActionsContextType>({
  setDraft: { action: "", available: false, unavailability_reason: null },
  close: { action: "", available: false, unavailability_reason: null },
  merge: { action: "", available: false, unavailability_reason: null },
  approve: { action: "", available: false, unavailability_reason: null },
  reject: { action: "", available: false, unavailability_reason: null },
});

export function usePcActionsContext() {
  const context = use(PcActionsContext);
  if (!context) {
    throw new Error("usePcActionsContext must be used within a PcActionsContextProvider.");
  }

  return context;
}
