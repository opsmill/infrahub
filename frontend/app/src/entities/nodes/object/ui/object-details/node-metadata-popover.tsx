import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { Button } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { PropertyList } from "@/shared/components/table/property-list";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { formatFullDate } from "@/shared/utils/date";

import { useGetNodeMetadata } from "@/entities/nodes/object/domain/get-node-metadata.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

function UserLink({ user }: { user: NodeCore | null }) {
  if (!user) return <>-</>;

  return <Link to={getObjectDetailsUrl(user.__typename, user.id)}>{getNodeLabel(user)}</Link>;
}

interface NodeMetadataProps {
  objectKind: string;
  objectId: string;
}

export function NodeMetadata({ objectKind, objectId }: NodeMetadataProps) {
  const { data, isPending, error } = useGetNodeMetadata({ objectKind, objectId });

  if (isPending) {
    return <LoadingIndicator className="h-36 w-50" />;
  }

  if (error) {
    return <ErrorScreen className="p-4" message={error.message} />;
  }

  if (!data) {
    return <ErrorScreen className="p-4" message="No metadata available" />;
  }

  const items = [
    {
      name: "Created at",
      value: formatFullDate(data.created_at),
    },
    {
      name: "Created by",
      value: <UserLink user={data.created_by} />,
    },
    {
      name: "Updated at",
      value: formatFullDate(data.updated_at),
    },
    {
      name: "Updated by",
      value: <UserLink user={data.updated_by} />,
    },
  ];

  return <PropertyList properties={items} valueClassName="text-right" />;
}

export function NodeMetadataPopover(props: NodeMetadataProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant="ghost"
          className="text-gray-500"
          data-testid="node-metadata-button"
        >
          <Icon icon="mdi:information-slab-circle-outline" />
        </Button>
      </PopoverTrigger>

      <PopoverContent>
        <NodeMetadata {...props} />
      </PopoverContent>
    </Popover>
  );
}
