import React from "react";

interface DismissGuardContextValue {
  setDismissable: (dismissable: boolean, onDismissAttempt?: () => void) => void;
}

export const DismissGuardContext = React.createContext<DismissGuardContextValue | null>(null);

export function useDismissGuard(onOpenChange?: (isOpen: boolean) => void) {
  const dismissableRef = React.useRef(true);
  const onDismissAttemptRef = React.useRef<(() => void) | undefined>(undefined);

  const setDismissable = (value: boolean, onDismissAttempt?: () => void) => {
    dismissableRef.current = value;
    onDismissAttemptRef.current = onDismissAttempt;
  };

  const guardedOnOpenChange = (isOpen: boolean) => {
    if (!isOpen && !dismissableRef.current) {
      onDismissAttemptRef.current?.();
      return;
    }
    onOpenChange?.(isOpen);
  };

  return { setDismissable, guardedOnOpenChange };
}
