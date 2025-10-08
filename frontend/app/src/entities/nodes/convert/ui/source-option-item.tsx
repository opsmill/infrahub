import type { ReactNode } from "react";

import { Badge } from "@/shared/components/ui/badge";

interface SourceOptionItemProps {
  optionLabel: ReactNode;
  sourceLabel: ReactNode;
  isDefaultMatch?: boolean;
}

export const SourceOptionItem = ({
  optionLabel,
  isDefaultMatch,
  sourceLabel,
}: SourceOptionItemProps) => {
  return (
    <div className="flex grow items-center justify-between">
      <span className="grow">{optionLabel}</span>

      <div className="space-x-2">
        {isDefaultMatch && <Badge variant={"blue-outline"}>Matched</Badge>}

        <Badge variant={"gray-outline"}>{sourceLabel}</Badge>
      </div>
    </div>
  );
};

interface SourceOptionValueProps {
  optionLabel: ReactNode;
  sourceLabel: ReactNode;
}

export const SourceOptionValue = ({ optionLabel, sourceLabel }: SourceOptionValueProps) => {
  return (
    <Badge className="space-x-1">
      <span>{optionLabel}</span>
      <span className="font-light text-gray-700">• {sourceLabel}</span>
    </Badge>
  );
};
