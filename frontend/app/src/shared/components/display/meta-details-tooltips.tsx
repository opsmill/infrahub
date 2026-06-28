import { Icon } from "@iconify-icon/react";
import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { FileBoxIcon } from "lucide-react";
import type React from "react";

import type { AnyAttribute } from "@/shared/api/graphql/generated/types";
import { PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";
import { formatFullDate, formatRelativeTimeFromNow } from "@/shared/utils/date";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface MetaDetailsTooltipProps {
  header?: React.ReactNode;
  updatedAt: AnyAttribute["updated_at"];
  source?: NodeCore | null;
  owner?: NodeCore | null;
  isProtected: AnyAttribute["is_protected"];
}

export default function MetaDetailsTooltip({
  header,
  updatedAt,
  source,
  owner,
  isProtected,
}: MetaDetailsTooltipProps) {
  const { isProfile, isTemplate } = useSchema(source?.__typename);

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
      value: updatedAt ? formatFullDate(updatedAt) : "-",
    },
    {
      name: "Update time",
      value: updatedAt ? formatRelativeTimeFromNow(updatedAt) : "-",
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
      <Button size="xs" shape="circle" variant="ghost" data-testid="view-metadata-button">
        <Icon icon="mdi:information-slab-circle-outline" />
      </Button>

      <Popover data-testid="metadata-tooltip">
        {!!header && header}

        <PropertyList properties={items} valueClassName="text-right" />
      </Popover>
    </PopoverTrigger>
  );
}
