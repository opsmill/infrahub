import { useState } from "react";

import type { AuthMethod } from "@/entities/authentication/auth-methods";
import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";

function pickInitial(methods: Array<AuthMethod>, defaultMethod?: AuthMethod): AuthMethod | null {
  const first = methods[0];
  if (!first) return null;
  const storedKind = localStorage.getItem(LAST_USED_METHOD_KEY);
  const found = storedKind ? methods.find((m) => m.kind === storedKind) : undefined;
  return found ?? defaultMethod ?? first;
}

export function useLastUsedMethod(
  methods: Array<AuthMethod>,
  defaultMethod?: AuthMethod
): [AuthMethod | null, (method: AuthMethod) => void] {
  const [active, setActiveState] = useState<AuthMethod | null>(() =>
    pickInitial(methods, defaultMethod)
  );

  const setActive = (method: AuthMethod) => {
    localStorage.setItem(LAST_USED_METHOD_KEY, method.kind);
    setActiveState(method);
  };

  return [active, setActive];
}
