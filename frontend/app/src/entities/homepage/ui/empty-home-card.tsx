import type { ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

interface EmptyHomeCardProps {
  title: ReactNode;
  subtitle?: ReactNode;
  className?: string;
}

export function EmptyHomeCard({ title, subtitle, className }: EmptyHomeCardProps) {
  return (
    <div className={classNames("flex h-full flex-col items-center justify-center", className)}>
      <div className="font-semibold">{title}</div>
      <div className="text-sm">{subtitle}</div>
    </div>
  );
}
