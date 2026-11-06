import { classNames } from "@/shared/utils/common";

import { useConfig } from "@/entities/config/ui/config-provider";
import { instanceBarClassName } from "@/entities/preferences/domain/rules/instance-color";

export function InstanceColorBar() {
  const { color } = useConfig().instance;
  const barClassName = instanceBarClassName(color);

  if (!barClassName) return null;

  return (
    <div
      aria-hidden
      data-testid="instance-color-bar"
      className={classNames("h-0.75 w-full shrink-0", barClassName)}
    />
  );
}
