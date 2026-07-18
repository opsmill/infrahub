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
        "bg-linear-to-b from-stone-50 to-10% to-white",
        "border border-neutral-200",
        "shadow-[0_1px_1px_rgba(0,0,0,0.02)] inset-shadow-[0_2px_0_rgb(255,255,255),0_-1px_2px_1px_rgba(0,0,0,0.03)]",
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
        "border-b border-b-neutral-200",
        "bg-linear-to-b from-neutral-100 to-neutral-50",
        "px-3 py-2",
        "font-medium text-neutral-700 text-sm tracking-tight",
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.85)]",
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
