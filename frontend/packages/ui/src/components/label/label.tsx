import { Label as AriaLabel, type LabelProps as AriaLabelProps } from "react-aria-components";
import { cn, tv } from "tailwind-variants";

const labelStyles = tv({
  base: [
    "cursor-pointer font-medium text-foreground text-sm leading-none",
    "data-disabled:cursor-not-allowed data-disabled:opacity-70",
  ],
});

export interface LabelProps extends AriaLabelProps {}

export function Label({ className, ...props }: LabelProps) {
  return <AriaLabel className={cn(labelStyles(), className)} {...props} />;
}
