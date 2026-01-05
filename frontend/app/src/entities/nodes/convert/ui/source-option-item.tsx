import type { ReactNode } from "react";

import { Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";

interface SourceOptionItemProps {
  optionLabel: ReactNode;
  sourceFieldName: ReactNode;
  isDefaultMatch?: boolean;
}

export const SourceOptionItem = ({
  optionLabel,
  isDefaultMatch,
  sourceFieldName,
}: SourceOptionItemProps) => {
  return (
    <div className="flex grow items-center justify-between">
      <span className="grow">{optionLabel}</span>

      <Row>
        {isDefaultMatch && <Badge variant={"blue-outline"}>Matched</Badge>}

        <Badge variant={"gray-outline"}>{sourceFieldName}</Badge>
      </Row>
    </div>
  );
};

interface SourceOptionValueProps {
  optionLabel: ReactNode;
  sourceFieldName: ReactNode;
}

export const SourceOptionValue = ({ optionLabel, sourceFieldName }: SourceOptionValueProps) => {
  return (
    <Badge className="space-x-1">
      <span>{optionLabel}</span>
      <span className="font-light text-gray-700">• {sourceFieldName}</span>
    </Badge>
  );
};
