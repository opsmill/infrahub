import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { InfoIcon } from "lucide-react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { PropertyList } from "@/shared/components/table/property-list";
import { Link } from "@/shared/components/ui/link";
import { useFormatDate } from "@/shared/context/date-preferences-context";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { useGetNodeMetadata } from "@/entities/nodes/object/ui/queries/get-node-metadata.query";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

function UserLink({ user }: { user: NodeCore | null }) {
  if (!user) return <>-</>;

  if (user.id === "__system__") {
    return <span>{user.display_label}</span>;
  }

  return <Link to={getObjectDetailsUrl(user.__typename, user.id)}>{getNodeLabel(user)}</Link>;
}

interface NodeMetadataProps {
  objectKind: string;
  objectId: string;
}

export function NodeMetadata({ objectKind, objectId }: NodeMetadataProps) {
  const { data, isPending, error } = useGetNodeMetadata({ objectKind, objectId });
  const { formatDate } = useFormatDate();

  if (isPending) {
    return <LoadingIndicator className="h-36 w-50" />;
  }

  if (error) {
    return <ErrorScreen className="p-4" message={error.message} />;
  }

  if (!data) {
    return <ErrorScreen className="p-4" message="No metadata available" />;
  }

  const { created_at, created_by, updated_at, updated_by } = data;

  const items = [
    {
      name: "Created at",
      value: created_at ? formatDate(created_at, "datetime") : "-",
    },
    {
      name: "Created by",
      value: <UserLink user={created_by} />,
    },
    {
      name: "Updated at",
      value: updated_at ? formatDate(updated_at, "datetime") : "-",
    },
    {
      name: "Updated by",
      value: <UserLink user={updated_by} />,
    },
  ];

  return <PropertyList properties={items} valueClassName="text-right" />;
}

export function NodeMetadataPopover(props: NodeMetadataProps) {
  return (
    <PopoverTrigger>
      <Button
        size="xs"
        shape="square"
        variant="ghost"
        className="text-foreground-muted"
        aria-label="View node metadata"
      >
        <InfoIcon />
      </Button>

      <Popover>
        <NodeMetadata {...props} />
      </Popover>
    </PopoverTrigger>
  );
}
