import { formatFullDate, formatRelativeTimeFromNow } from "@/utils/date";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { AnyAttribute } from "../../generated/graphql";
import { Button } from "../buttons/button-primitive";
import { PropertyList } from "../table/property-list";
import { Badge } from "../ui/badge";
import { Link } from "../ui/link";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

interface MetaDetailsTooltipProps {
  header?: React.ReactNode;
  updatedAt: AnyAttribute["updated_at"];
  source: AnyAttribute["source"] & { __typename: string };
  owner: AnyAttribute["owner"] & { __typename: string };
  isFromProfile?: AnyAttribute["is_from_profile"];
  isProtected: AnyAttribute["is_protected"];
}

export default function MetaDetailsTooltip({
  header,
  updatedAt,
  source,
  owner,
  isFromProfile,
  isProtected,
}: MetaDetailsTooltipProps) {
  const items = [
    {
      name: "Source",
      value: source ? (
        <Link to={constructPath(`/objects/${source.__typename}/${source.id}`)}>
          {isFromProfile ? (
            <Badge variant="green" className="font-normal hover:underline">
              <Icon icon="mdi:shape-plus-outline" className="mr-1" />
              {source.display_label}
            </Badge>
          ) : (
            source.display_label
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
        <Link to={constructPath(`/objects/${owner.__typename}/${owner.id}`)}>
          {owner.display_label}
        </Link>
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
          data-testid="view-metadata-button">
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
