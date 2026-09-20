import { composeRenderProps } from "react-aria-components";
import { cn } from "tailwind-variants";

export function composeAriaClassName<TValue>(
  className: string | ((value: TValue) => string) | undefined,
  tailwind?: string | ((value: TValue) => string | undefined)
): string | ((value: TValue) => string) {
  return composeRenderProps(className, (resolvedClassName, renderProps): string => {
    const tw = typeof tailwind === "function" ? tailwind(renderProps) : tailwind;
    return cn(tw, resolvedClassName) ?? "";
  });
}
