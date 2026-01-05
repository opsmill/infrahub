import * as LabelPrimitive from "@radix-ui/react-label";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { classNames } from "@/shared/utils/common";

export interface LabelProps
  extends React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>,
    VariantProps<typeof labelVariants> {}

const labelVariants = cva(
  "cursor-pointer peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
  {
    variants: {
      variant: {
        default: "font-medium text-gray-900 text-sm",
        small: "font-normal text-xs",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

const Label = React.forwardRef<React.ElementRef<typeof LabelPrimitive.Root>, LabelProps>(
  ({ className, variant, ...props }, ref) => (
    <LabelPrimitive.Root
      ref={ref}
      className={classNames(labelVariants({ variant }), className)}
      {...props}
    />
  )
);

export default Label;
