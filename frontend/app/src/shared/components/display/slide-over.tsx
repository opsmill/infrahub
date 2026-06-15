import { Icon } from "@iconify-icon/react";
import type React from "react";

import { Badge } from "@/shared/components/ui/badge";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import type { ModelSchema } from "@/entities/schema/types";

type SlideOverTitleProps = {
  schema: ModelSchema;
  currentObjectLabel?: string | null;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
};

export const SlideOverTitle = ({
  currentObjectLabel,
  schema,
  title,
  subtitle,
}: SlideOverTitleProps) => {
  const { currentBranch } = useCurrentBranch();

  return (
    <div className="space-y-2">
      <div className="flex">
        <Badge variant="blue" className="flex items-center gap-1">
          <Icon icon="mdi:layers-triple" />
          <span>{currentBranch.name}</span>
        </Badge>

        <ObjectHelpButton
          kind={schema.kind}
          documentationUrl={schema.documentation}
          className="ml-auto"
        />
      </div>

      <div className="flex justify-between">
        <div className="flex w-full items-center gap-2 whitespace-nowrap text-sm">
          {schema.label}

          {currentObjectLabel && (
            <>
              <Icon icon="mdi:chevron-right" />

              <span className="truncate">{currentObjectLabel}</span>
            </>
          )}
        </div>
      </div>

      <div>
        {title && <h3 className="font-semibold text-lg">{title}</h3>}
        {subtitle && <p className="text-sm">{subtitle}</p>}
      </div>
    </div>
  );
};
