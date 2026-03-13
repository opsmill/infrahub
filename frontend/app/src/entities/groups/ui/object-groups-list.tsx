import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Link } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import type { GroupData } from "@/entities/groups/domain/types";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useRemoveRelationships } from "@/entities/nodes/relationships/ui/queries/remove-relationships.mutation";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface ObjectGroupsListProps {
  className?: string;
  objectId: string;
  groups: Array<GroupData>;
}

export function ObjectGroupsList({ className, objectId, groups }: ObjectGroupsListProps) {
  if (groups.length === 0) {
    return <p className="py-4 text-center">There are no groups to display.</p>;
  }

  return (
    <div className={classNames("space-y-4", className)}>
      {groups.map((group) => (
        <ObjectGroupItem objectId={objectId} key={group.id} group={group} />
      ))}
    </div>
  );
}

interface ObjectGroupItemProps {
  objectId: string;
  group: GroupData;
}

function ObjectGroupItem({ objectId, group }: ObjectGroupItemProps) {
  const { schema: groupSchema } = useSchema(group.__typename);

  return (
    <Row className="relative justify-between gap-4 rounded-md border border-gray-300 bg-gray-100 p-2">
      <div className="space-y-1 overflow-hidden">
        <Link
          to={getObjectDetailsUrl(group.__typename, group.id)}
          className="block truncate font-semibold hover:underline"
        >
          {getNodeLabel(group)}
        </Link>

        <Row>
          <Link
            to={getObjectDetailsUrl(group.__typename, group.id, [
              { name: QSP.TAB, value: "members" },
            ])}
            className="font-light text-sm hover:underline"
          >
            {pluralize(group.members.count, "member")}
          </Link>

          <Link to={getObjectDetailsUrl(group.__typename)}>
            <Badge variant="blue" className="hover:underline">
              {groupSchema?.label}
            </Badge>
          </Link>
        </Row>

        {group.description && <p className="text-xs">{group.description.value}</p>}
      </div>

      <RemoveGroupButton objectId={objectId} group={group} />
    </Row>
  );
}

function RemoveGroupButton({ objectId, group }: ObjectGroupItemProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const { mutate: removeRelationships, isPending } = useRemoveRelationships();

  const handleRemoveGroup = () => {
    removeRelationships(
      {
        objectId,
        relationshipName: "member_of_groups",
        relationshipIds: [group.id],
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
          setShowDeleteModal(false);
        },
      }
    );
  };

  return (
    <>
      <Tooltip content="Leave" enabled>
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0 hover:bg-gray-200"
          onClick={() => setShowDeleteModal(true)}
          data-testid="leave-group-button"
        >
          <Icon icon="mdi:link-variant-remove" className="text-lg text-red-600" />
        </Button>
      </Tooltip>

      <ModalDelete
        title="Leave Group"
        description={`Are you sure you want to leave group ${getNodeLabel(group)}?`}
        onDelete={handleRemoveGroup}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        isLoading={isPending}
      />
    </>
  );
}
