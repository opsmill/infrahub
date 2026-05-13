import { Button } from "@infrahub/ui";

import { classNames } from "@/shared/utils/common";

import type { AuthMethod, AuthMethodKind } from "@/entities/authentication/types";
import { LocalCredentialsForm } from "@/entities/authentication/ui/local-credentials-form";
import { LoginWithSSOButtons } from "@/entities/authentication/ui/login-sso-buttons";
import { useAvailableAuthMethods } from "@/entities/authentication/ui/use-available-auth-methods";
import { useLastUsedMethod } from "@/entities/authentication/ui/use-last-used-method";

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
      return <LoginWithSSOButtons providers={method.providers} className="fade-in animate-in" />;
  }
}

// When multiple methods are available and no preference is stored, prefer SSO
// to preserve the existing default UX. Stored preferences override this.
function preferredDefault(methods: Array<AuthMethod>): AuthMethod | undefined {
  if (methods.length === 0) return;
  return methods.find((m) => m.kind === "sso") ?? methods[0];
}

export const LoginMethodPicker = () => {
  const methods = useAvailableAuthMethods();
  const [active, setActive] = useLastUsedMethod(methods, preferredDefault(methods));

  if (methods.length === 0 || !active) {
    return <p className="text-red-500 text-sm">No authentication method available.</p>;
  }

  const others = methods.filter((m) => m.kind !== active.kind);

  return (
    <>
      <MethodContent method={active} />
      {others.map((m) => (
        <Button
          key={m.kind}
          variant="ghost"
          onPress={() => setActive(m)}
          className={classNames(
            "text-cyan-900 text-sm",
            "data-hovered:bg-transparent data-hovered:underline"
          )}
        >
          {TOGGLE_LABEL[m.kind]}
        </Button>
      ))}
    </>
  );
};
