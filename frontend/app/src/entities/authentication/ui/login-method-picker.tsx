import { Button } from "@infrahub/ui";

import { classNames } from "@/shared/utils/common";

import {
  AUTH_METHODS,
  type AuthMethod,
  getAuthMethodToggleLabel,
  renderAuthMethod,
} from "@/entities/authentication/auth-methods";
import { useAvailableAuthMethods } from "@/entities/authentication/ui/use-available-auth-methods";
import { useLastUsedMethod } from "@/entities/authentication/ui/use-last-used-method";

// When no preference is stored, prefer the method marked `preferDefault` in
// the registry. Stored preferences always win.
function preferredDefault(methods: Array<AuthMethod>): AuthMethod | undefined {
  return methods.find((m) => AUTH_METHODS[m.kind].preferDefault) ?? methods[0];
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
      {renderAuthMethod(active)}
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
          {getAuthMethodToggleLabel(m)}
        </Button>
      ))}
    </>
  );
};
