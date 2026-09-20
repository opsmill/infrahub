import type { ReactNode } from "react";
import { Meter as AriaMeter, type MeterProps as AriaMeterProps } from "react-aria-components";
import { cn } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

export interface MeterProps extends AriaMeterProps {
  label?: ReactNode;
}

export function Meter({ label, className, ...props }: MeterProps) {
  return (
    <AriaMeter
      {...props}
      className={composeAriaClassName(
        className,
        label
          ? "grid w-full grid-cols-[1fr_auto] items-center gap-x-2"
          : "flex w-full items-center gap-2"
      )}
    >
      {({ percentage, valueText }) => {
        const track = (
          <div
            className={cn(
              "h-2.5 overflow-hidden rounded-full bg-border",
              "inset-shadow-[0_1px_2px_rgba(0,0,0,0.15)] ring-1 ring-border-strong ring-inset",
              label ? "col-span-2 w-full" : "grow"
            )}
          >
            <div
              className={cn(
                "h-full rounded-[inherit] transition-all",
                "border border-cyan-800 bg-linear-to-b from-cyan-800 to-cyan-600",
                "inset-shadow-[0_1px_0_rgba(255,255,255,0.4)]"
              )}
              style={{ width: `${percentage}%` }}
            />
          </div>
        );

        const value = <span className="font-medium text-accent">{valueText}</span>;

        if (label) {
          return (
            <>
              <span className="font-medium text-sm">{label}</span>
              {value}
              {track}
            </>
          );
        }

        return (
          <>
            {track}
            {value}
          </>
        );
      }}
    </AriaMeter>
  );
}
