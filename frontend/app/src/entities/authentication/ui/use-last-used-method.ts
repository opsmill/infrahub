import { useState } from "react";

import {
  AUTH_METHODS,
  type AuthMethod,
  type AuthMethodKind,
} from "@/entities/authentication/auth-methods";
import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";

function readStoredKind(): AuthMethodKind | null {
  const raw = localStorage.getItem(LAST_USED_METHOD_KEY);
  return raw !== null && raw in AUTH_METHODS ? (raw as AuthMethodKind) : null;
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

  // Resolve from `methods` every render so providers stay fresh and a method
  // that becomes unavailable falls back gracefully. `defaultMethod` is only
  // honored if it's actually in `methods`, so callers can't surface a method
  // that isn't available.
  const active =
    methods.find((m) => m.kind === activeKind) ??
    methods.find((m) => m.kind === defaultMethod?.kind) ??
    methods[0] ??
    null;

  return [active, setActive];
}
