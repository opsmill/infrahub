import type React from "react";
import { cn, tv, type VariantProps } from "tailwind-variants";

const cardVariants = tv({
  base: "flex flex-col rounded-2xl border",
  variants: {
    variant: {
      card: "bg-card shadow-card",
      secondary: "bg-secondary shadow-secondary",
      panel: "border-border-strong bg-panel shadow-panel",
    },
  },
  defaultVariants: {
    variant: "card",
  },
});

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  ref?: React.Ref<HTMLDivElement>;
}

export function Card({ className, ref, variant, ...props }: CardProps) {
  return <div ref={ref} className={cardVariants({ variant, class: className })} {...props} />;
}

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
}

export function CardHeader({ className, ref, ...props }: CardHeaderProps) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-t-[inherit]",
        "border-b",
        "bg-card-header",
        "px-3 py-2",
        "font-medium text-card-header-foreground text-sm tracking-tight",
        "shadow-card-header",
        className
      )}
      {...props}
    />
  );
}

export interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
}

export function CardContent({ className, ref, ...props }: CardContentProps) {
  return <div ref={ref} className={cn("p-3", className)} {...props} />;
}
