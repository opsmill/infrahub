import { useState } from "react";

import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/auth-methods";
import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";

function readStoredKind(): AuthMethodKind | null {
  return (localStorage.getItem(LAST_USED_METHOD_KEY) as AuthMethodKind | null) ?? null;
}

export function useLastUsedMethod(
  methods: Array<AuthMethod>,
  defaultMethod?: AuthMethod
): [AuthMethod | null, (method: AuthMethod) => void] {
  const [activeKind, setActiveKind] = useState<AuthMethodKind | null>(readStoredKind);

  const setActive = (method: AuthMethod) => {
    localStorage.setItem(LAST_USED_METHOD_KEY, method.kind);
    setActiveKind(method.kind);
  };

  // Resolve from current methods every render so providers stay fresh and a
  // method that becomes unavailable falls back gracefully.
  const active = methods.find((m) => m.kind === activeKind) ?? defaultMethod ?? methods[0] ?? null;

  return [active, setActive];
}
