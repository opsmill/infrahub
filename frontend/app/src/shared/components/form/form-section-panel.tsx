import { Card, CardContent, CardHeader } from "@infrahub/ui";
import React from "react";

import { SectionTitle } from "@/entities/nodes/object/ui/object-details/section-title";

interface FormSectionPanelProps {
  label: React.ReactNode;
  description?: string | null;
  children: React.ReactNode;
}

export function FormSectionPanel({ label, description, children }: FormSectionPanelProps) {
  const id = React.useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;

  return (
    <Card variant="panel" role="region" aria-labelledby={titleId}>
      <CardHeader>
        <SectionTitle
          label={label}
          description={description}
          titleId={titleId}
          descriptionId={descriptionId}
        />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  );
}
