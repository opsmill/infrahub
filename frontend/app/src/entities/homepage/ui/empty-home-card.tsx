import type { ReactNode } from "react";

interface EmptyHomeCardProps {
  title: ReactNode;
  subtitle?: ReactNode;
}

export function EmptyHomeCard({ title, subtitle }: EmptyHomeCardProps) {
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-6 text-stone-500">
      <div className="font-medium text-lg">{title}</div>
      <div className="text-sm">{subtitle}</div>
    </div>
  );
}
