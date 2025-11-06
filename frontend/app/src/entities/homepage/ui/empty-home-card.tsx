import type { ReactNode } from "react";

interface EmptyHomeCardProps {
  title: ReactNode;
  subtitle?: ReactNode;
}

export function EmptyHomeCard({ title, subtitle }: EmptyHomeCardProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center">
      <div className="font-semibold">{title}</div>
      <div className="text-sm">{subtitle}</div>
    </div>
  );
}
