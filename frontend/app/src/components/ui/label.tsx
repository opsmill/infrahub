import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cva, type VariantProps } from "class-variance-authority";
import { classNames } from "@/utils/common";

export interface LabelProps
  extends React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>,
    VariantProps<typeof labelVariants> {}

const labelVariants = cva(
  "text-sm font-medium text-gray-900 cursor-pointer peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
);

const Label = React.forwardRef<React.ElementRef<typeof LabelPrimitive.Root>, LabelProps>(
  ({ className, ...props }, ref) => (
    <LabelPrimitive.Root ref={ref} className={classNames(labelVariants(), className)} {...props} />
  )
);

export default Label;
