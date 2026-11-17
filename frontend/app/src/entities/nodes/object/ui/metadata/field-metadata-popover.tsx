import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { FileBoxIcon } from "lucide-react";
import type React from "react";

import { Icon } from "@/shared/components/display/icon";
import { PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";
import { useFormatDate } from "@/shared/context/date-preferences-context";

import type {
  NodeAttributeMetadata,
  NodeRelationshipMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

// Hovering an element with this class reveals every metadata icon inside it that is set to reveal on hover.
export const METADATA_HOVER_AREA = "group/metadata";

interface FieldMetadataPopoverProps {
  metadata: NodeAttributeMetadata | NodeRelationshipMetadata;
  header?: React.ReactNode;
  revealOnHover?: boolean;
}

export function FieldMetadataPopover({
  metadata,
  header,
  revealOnHover = false,
}: FieldMetadataPopoverProps) {
  const { source, owner, updated_at: updatedAt, is_protected: isProtected } = metadata;
  const { isProfile, isTemplate } = useSchema(source?.__typename);
  const { formatDate } = useFormatDate();

  const items = [
    {
      name: "Source",
      value: source ? (
        <Link to={getObjectDetailsUrl(source.__typename, source.id)}>
          {isProfile ? (
            <Badge variant="green" className="font-normal hover:underline">
              <Icon icon="mdi:shape-plus-outline" className="mr-1" /> {getNodeLabel(source)}
            </Badge>
          ) : isTemplate ? (
            <Badge variant="blue" className="font-normal hover:underline">
              <FileBoxIcon className="mr-1 size-3" /> {getNodeLabel(source)}
            </Badge>
          ) : (
            getNodeLabel(source)
          )}
        </Link>
      ) : (
        "-"
      ),
    },
    {
      name: "Updated at",
      value: updatedAt ? formatDate(updatedAt, "datetime") : "-",
    },
    {
      name: "Update time",
      value: updatedAt ? formatDate(updatedAt, "relative") : "-",
    },
    {
      name: "Owner",
      value: owner ? (
        <Link to={getObjectDetailsUrl(owner.__typename, owner.id)}>{getNodeLabel(owner)}</Link>
      ) : (
        "-"
      ),
    },
    {
      name: "Is protected",
      value: isProtected ? "True" : "False",
    },
  ];

  return (
    <PopoverTrigger>
      <Button
        size="xs"
        shape="circle"
        variant="ghost"
        className="text-foreground-muted"
        aria-label="View metadata"
        data-testid="view-metadata-button"
      >
        <Icon
          icon="mdi:information-slab-circle-outline"
          className={
            revealOnHover
              ? "in-aria-expanded:opacity-100 in-focus-visible:opacity-100 opacity-0 group-hover/metadata:opacity-100"
              : undefined
          }
        />
      </Button>

      <Popover data-testid="metadata-tooltip">
        {!!header && header}

        <PropertyList properties={items} valueClassName="text-right" />
      </Popover>
    </PopoverTrigger>
  );
}
