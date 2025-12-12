import { Icon } from "@iconify-icon/react";
import { FileBoxIcon } from "lucide-react";
import type React from "react";

import type { AnyAttribute } from "@/shared/api/graphql/generated/graphql";
import { Button } from "@/shared/components/buttons/button-primitive";
import { PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
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
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant="ghost"
          className="text-gray-500 focus-visible:ring-0"
          data-cy="metadata-button"
          data-testid="view-metadata-button"
        >
          <Icon icon="mdi:information-slab-circle-outline" />
        </Button>
      </PopoverTrigger>

      <PopoverContent data-testid="metadata-tooltip" data-cy="metadata-tooltip">
        {!!header && header}

        <PropertyList properties={items} valueClassName="text-right" />
      </PopoverContent>
    </Popover>
  );
}
