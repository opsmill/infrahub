import { useState } from "react";

import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";
import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/types";

function pickInitial(
  methods: Array<AuthMethod>,
  defaultMethod?: AuthMethod
): AuthMethod | null {
  if (methods.length === 0) return null;
  const storedKind = localStorage.getItem(LAST_USED_METHOD_KEY) as AuthMethodKind | null;
  const found = storedKind ? methods.find((m) => m.kind === storedKind) : undefined;
  return found ?? defaultMethod ?? methods[0];
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
