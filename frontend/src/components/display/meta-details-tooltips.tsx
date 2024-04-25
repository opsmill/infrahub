import React from "react";
import { PropertyList } from "../table/property-list";
import { Icon } from "@iconify-icon/react";
import { Button } from "../buttons/button-primitive";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { formatFullDate, formatRelativeTimeFromNow } from "../../utils/date";
import { Link } from "../utils/link";
import { constructPath } from "../../utils/fetch";
import { AnyAttribute } from "../../generated/graphql";
import { Badge } from "../ui/badge";

interface MetaDetailsTooltipProps {
  header?: React.ReactNode;
  updatedAt: AnyAttribute["updated_at"];
  source: AnyAttribute["source"] & { __typename: string };
  owner: AnyAttribute["owner"] & { __typename: string };
  isFromProfile?: AnyAttribute["is_from_profile"];
  isProtected: AnyAttribute["is_protected"];
  isInherited: AnyAttribute["is_inherited"];
}

export default function MetaDetailsTooltip({
  header,
  updatedAt,
  source,
  owner,
  isFromProfile,
  isProtected,
  isInherited,
}: MetaDetailsTooltipProps) {
  const items = [
    {
      name: "Source",
      value: source ? (
        isFromProfile ? (
          <Link to={constructPath(`/objects/CoreProfile/${source.id}`)}>
            <Badge variant="green" className="font-normal hover:underline">
              <Icon icon="mdi:shape-plus-outline" className="mr-1" />
              {source.display_label}
            </Badge>
          </Link>
        ) : (
          <Link to={constructPath(`/objects/${source.__typename}/${source.id}`)}>
            {source.display_label}
          </Link>
        )
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
    {
      name: "Is inherited",
      value: isInherited ? "True" : "False",
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
