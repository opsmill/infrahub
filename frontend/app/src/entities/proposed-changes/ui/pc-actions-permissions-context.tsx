import { createContext, use } from "react";

export interface PcActionsContextType {
  approve: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };

  cancelApprove: {
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

  reject: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };

  cancelReject: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };

  setDraft: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };

  unsetDraft: {
    action: string;
    available: boolean;
    unavailability_reason: string | null;
  };
}

export const PcActionsContext = createContext<PcActionsContextType>({
  approve: { action: "", available: false, unavailability_reason: null },
  cancelApprove: { action: "", available: false, unavailability_reason: null },
  close: { action: "", available: false, unavailability_reason: null },
  merge: { action: "", available: false, unavailability_reason: null },
  reject: { action: "", available: false, unavailability_reason: null },
  cancelReject: { action: "", available: false, unavailability_reason: null },
  setDraft: { action: "", available: false, unavailability_reason: null },
  unsetDraft: { action: "", available: false, unavailability_reason: null },
});

export function usePcActionsContext() {
  const context = use(PcActionsContext);
  if (!context) {
    throw new Error("usePcActionsContext must be used within a PcActionsContextProvider.");
  }

  return context;
}
