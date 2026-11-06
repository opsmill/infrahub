import type React from "react";

interface SectionTitleProps {
  label: React.ReactNode;
  description?: string | null;
  titleId: string;
  descriptionId: string;
}

export function SectionTitle({ label, description, titleId, descriptionId }: SectionTitleProps) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <h2 id={titleId} className="flex min-w-0 items-center gap-2 whitespace-nowrap">
        {label}
      </h2>
      {description && (
        <p id={descriptionId} className="font-normal text-foreground-muted text-xs">
          {description}
        </p>
      )}
    </div>
  );
}
