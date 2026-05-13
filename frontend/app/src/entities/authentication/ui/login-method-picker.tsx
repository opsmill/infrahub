import { useState } from "react";

import { LAST_USED_METHOD_KEY } from "@/entities/authentication/constants";
import { classNames } from "@/shared/utils/common";

import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/types";
import { LocalCredentialsForm } from "@/entities/authentication/ui/local-credentials-form";
import { LoginWithSSOButtons } from "@/entities/authentication/ui/login-sso-buttons";
import { useAvailableAuthMethods } from "@/entities/authentication/ui/use-available-auth-methods";

const TOGGLE_LABEL: Record<AuthMethodKind, string> = {
  local: "Log in with your credentials",
  sso: "Log in with SSO",
  // Future: ldap: "Log in with LDAP",
};

function MethodContent({ method }: { method: AuthMethod }) {
  switch (method.kind) {
    case "local":
      return <LocalCredentialsForm className="fade-in animate-in" />;
    case "sso":
      return (
        <LoginWithSSOButtons providers={method.providers} className="fade-in animate-in" />
      );
  }
}

// When multiple methods are available and no preference is stored, prefer SSO
// to preserve the existing default UX. Stored preferences override this.
function pickInitialMethod(methods: Array<AuthMethod>): AuthMethod | null {
  if (methods.length === 0) return null;

  const storedKind = localStorage.getItem(LAST_USED_METHOD_KEY) as AuthMethodKind | null;

  if (storedKind) {
    const found = methods.find((m) => m.kind === storedKind);
    if (found) return found;
  }

  // No stored preference — prefer SSO when available (preserves existing UX).
  return methods.find((m) => m.kind === "sso") ?? methods[0];
}

export const LoginMethodPicker = () => {
  const methods = useAvailableAuthMethods();
  const [active, setActiveState] = useState<AuthMethod | null>(() =>
    pickInitialMethod(methods)
  );

  if (methods.length === 0 || !active) {
    return <p className="text-red-500 text-sm">No authentication method available.</p>;
  }

  const setActive = (method: AuthMethod) => {
    localStorage.setItem(LAST_USED_METHOD_KEY, method.kind);
    setActiveState(method);
  };

  const others = methods.filter((m) => m.kind !== active.kind);

  return (
    <>
      <MethodContent method={active} />
      {others.map((m) => (
        <button
          key={m.kind}
          type="button"
          onClick={() => setActive(m)}
          className={classNames(
            "relative inline-flex shrink-0 cursor-pointer items-center justify-center",
            "whitespace-nowrap rounded-lg border-transparent text-cyan-900 text-sm",
            "shadow-none outline-none transition-all duration-150 ease-out",
            "h-9 gap-2 px-3",
            "hover:bg-transparent hover:underline"
          )}
        >
          {TOGGLE_LABEL[m.kind]}
        </button>
      ))}
    </>
  );
};
