import { Icon } from "@iconify-icon/react";

import { classNames } from "@/shared/utils/common";

export function ServiceEntryIcon({ icon, className }: { icon: string | null; className?: string }) {
  return (
    <div
      className={classNames(
        "flex shrink-0 items-center justify-center rounded-lg bg-custom-blue-700/10 text-custom-blue-700",
        className
      )}
    >
      <Icon icon={icon ?? "mdi:package-variant-closed"} />
    </div>
  );
}
