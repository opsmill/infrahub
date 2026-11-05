import { Button, Card, CardHeader } from "@infrahub/ui";
import { ChevronRightIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";
import { Disclosure, DisclosurePanel, Button as DisclosureTrigger } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { hasExtraFields } from "@/entities/nodes/object/domain/rules/has-extra-fields";
import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { SectionTitle } from "@/entities/nodes/object/ui/object-details/section-title";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
  excludeRelationships?: string[];
  title?: React.ReactNode;
  description?: string | null;
  defaultCollapsed?: boolean;
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
  excludeRelationships,
  title = "Details",
  description,
  defaultCollapsed,
}: ObjectDetailsCardProps) {
  const id = React.useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;
  const [showExtra, setShowExtra] = React.useState(false);
  const schemaHasExtraFields = hasExtraFields(objectSchema);

  const extraButton = schemaHasExtraFields && (
    <Button
      variant="ghost"
      size="sm"
      className="h-auto gap-1 pr-0 text-xs"
      onPress={() => setShowExtra((prev) => !prev)}
    >
      {showExtra ? <EyeOffIcon className="size-3.5" /> : <EyeIcon className="size-3.5" />}
      Extra
    </Button>
  );

  const dataDisplay = (
    <ObjectDataDisplay
      objectSchema={objectSchema}
      objectData={objectData}
      permission={permission}
      showExtra={showExtra}
      excludeRelationships={excludeRelationships}
    />
  );

  if (defaultCollapsed === undefined) {
    return (
      <Card
        className={className}
        role="region"
        aria-labelledby={titleId}
        data-testid="object-details"
      >
        <CardHeader className="flex items-center justify-between gap-2">
          <SectionTitle
            label={title}
            description={description}
            titleId={titleId}
            descriptionId={descriptionId}
          />
          {extraButton}
        </CardHeader>

        {dataDisplay}
      </Card>
    );
  }

  return (
    <Card
      className={className}
      role="region"
      aria-labelledby={titleId}
      data-testid="object-details"
    >
      <Disclosure defaultExpanded={!defaultCollapsed}>
        {({ isExpanded }) => (
          <>
            <CardHeader className="flex items-center justify-between gap-2">
              <SectionTitle
                label={
                  <DisclosureTrigger
                    slot="trigger"
                    aria-describedby={description ? descriptionId : undefined}
                    className="-ml-1 flex min-w-0 items-center gap-1 rounded-sm px-1 text-left focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <ChevronRightIcon
                      aria-hidden
                      className={classNames(
                        "size-3.5 shrink-0 transition-transform duration-150 ease-out motion-reduce:transition-none",
                        isExpanded && "rotate-90"
                      )}
                    />
                    {title}
                  </DisclosureTrigger>
                }
                description={description}
                titleId={titleId}
                descriptionId={descriptionId}
              />
              {extraButton}
            </CardHeader>

            <DisclosurePanel>{dataDisplay}</DisclosurePanel>
          </>
        )}
      </Disclosure>
    </Card>
  );
}
