import { Button } from "@infrahub/ui";

import { classNames } from "@/shared/utils/common";

import { AUTH_METHODS, getAuthMethodDefinition } from "@/entities/authentication/auth-methods";
import type { AuthMethod } from "@/entities/authentication/types";
import { useAvailableAuthMethods } from "@/entities/authentication/ui/use-available-auth-methods";
import { useLastUsedMethod } from "@/entities/authentication/ui/use-last-used-method";

// When multiple methods are available and no preference is stored, prefer the
// method marked as `preferDefault` in the registry. Stored preferences override this.
function preferredDefault(methods: Array<AuthMethod>): AuthMethod | undefined {
  return methods.find((m) => AUTH_METHODS[m.kind].preferDefault) ?? methods[0];
}

function renderMethod(method: AuthMethod) {
  // The registry's render is typed against the matching variant of AuthMethod,
  // which TS can't narrow through the dynamic lookup — cast to the broadest signature.
  const { render } = getAuthMethodDefinition(method.kind);
  return (render as (m: AuthMethod) => React.ReactNode)(method);
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
      {renderMethod(active)}
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
          {AUTH_METHODS[m.kind].toggleLabel}
        </Button>
      ))}
    </>
  );
};
