import { Button, Card, CardHeader } from "@infrahub/ui";
import { ChevronRightIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";
import { Disclosure, DisclosurePanel, Button as DisclosureTrigger } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import type { FieldSection } from "@/entities/nodes/object/domain/model/field-section";
import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import {
  getDataDisplayFields,
  ObjectDataDisplay,
} from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { SectionTitle } from "@/entities/nodes/object/ui/object-details/section-title";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
  excludeRelationships?: string[];
  fieldNames?: string[];
  title?: React.ReactNode;
  section?: FieldSection<unknown>["container"];
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
  excludeRelationships,
  fieldNames,
  title = "Details",
  section,
}: ObjectDetailsCardProps) {
  const id = React.useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;
  const [showExtra, setShowExtra] = React.useState(false);
  const fields = getDataDisplayFields({ objectSchema, excludeRelationships, fieldNames });
  const hasExtraFields = fields.some((field) => field.display === "extra");
  const description = section?.description;

  const extraButton = hasExtraFields && (
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
      fieldNames={fieldNames}
    />
  );

  const header = (isExpanded: boolean) => (
    <CardHeader
      className={classNames(
        "flex items-center justify-between gap-2",
        // biome-ignore lint/nursery/noTailwindArbitraryValue: no-utility: inherit is a CSS keyword, not a scale value
        !isExpanded && "rounded-[inherit] border-b-0"
      )}
    >
      <SectionTitle
        label={
          section === undefined ? (
            title
          ) : (
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
              {section.label}
            </DisclosureTrigger>
          )
        }
        description={description}
        titleId={titleId}
        descriptionId={descriptionId}
      />
      {isExpanded && extraButton}
    </CardHeader>
  );

  return (
    <Card
      className={className}
      role="region"
      aria-labelledby={titleId}
      {...(section === undefined
        ? { "data-testid": "object-details" }
        : { "data-testid": "object-details-section", "data-section": section.name })}
    >
      {section === undefined ? (
        <>
          {header(true)}
          {dataDisplay}
        </>
      ) : (
        // biome-ignore lint/nursery/noTailwindArbitraryValue: no-utility: inherit is a CSS keyword, not a scale value
        <Disclosure defaultExpanded={!section.collapsed} className="rounded-[inherit]">
          {({ isExpanded }) => (
            <>
              {header(isExpanded)}
              <DisclosurePanel>{dataDisplay}</DisclosurePanel>
            </>
          )}
        </Disclosure>
      )}
    </Card>
  );
}
