import type React from "react";

import { cn } from "tailwind-variants";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
}

export function Card({ className, ref, ...props }: CardProps) {
  return (
    <div
      ref={ref}
      className={cn(
        "flex flex-col",
        "rounded-2xl",
        "bg-card",
        "border border-card-border",
        "shadow-card",
        className,
      )}
      {...props}
    />
  );
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
        "border-b border-b-card-border",
        "bg-card-header",
        "px-3 py-2",
        "text-sm font-medium tracking-tight text-card-header-foreground",
        "shadow-card-header",
        className,
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
