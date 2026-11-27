import type React from "react";

import { classNames } from "@/shared/utils/common";

export const UNSET_FIELD_VALUE = "-";

export interface IpPoolFieldProps {
  label: string;
  children: React.ReactNode;
}

export function IpPoolField({ label, children }: IpPoolFieldProps) {
  return (
    <div className="contents">
      <dt className="whitespace-nowrap text-foreground-muted text-xs">{label}</dt>
      <dd className="-m-0.5 truncate p-0.5 font-medium text-foreground">{children}</dd>
    </div>
  );
}

export interface IpPoolFieldListProps extends React.ComponentProps<"dl"> {}

export function IpPoolFieldList({ className, ...props }: IpPoolFieldListProps) {
  return (
    <dl
      className={classNames(
        // biome-ignore lint/nursery/noTailwindArbitraryValue: no-utility: auto-cols-max stops values from truncating and grid-rows-2 makes the label row as tall as the value row
        "grid min-w-0 auto-cols-[minmax(auto,max-content)] grid-flow-col grid-rows-[auto_auto] gap-x-8 gap-y-1",
        className
      )}
      {...props}
    />
  );
}
