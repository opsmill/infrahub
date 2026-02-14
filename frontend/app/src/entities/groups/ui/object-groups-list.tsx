import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { Link } from "react-router";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import type { GroupDataFromAPI } from "@/entities/groups/api/types";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useRemoveRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships.mutation";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

type ObjectGroupsListProps = {
  className?: string;
  objectId: string;
  groups: Array<GroupDataFromAPI>;
};

export default function ObjectGroupsList({ className, objectId, groups }: ObjectGroupsListProps) {
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

type ObjectGroupProps = {
  objectId: string;
  group: GroupDataFromAPI;
};

const ObjectGroupItem = ({ objectId, group }: ObjectGroupProps) => {
  const nodes = useAtomValue(nodeSchemasAtom);
  const groupSchema = nodes.find((node) => node.kind === group.__typename);

  return (
    <div className="relative flex items-center justify-between gap-4 rounded-md border border-gray-300 bg-gray-100 p-2">
      <div className="space-y-1 overflow-hidden">
        <Link
          to={getObjectDetailsUrl(group.__typename, group.id)}
          className="block truncate font-semibold hover:underline"
        >
          {getNodeLabel(group)}
        </Link>

        <div className="flex items-center gap-2">
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
        </div>

        {group.description && <p className="text-xs">{group.description.value}</p>}
      </div>

      {objectId && <RemoveGroupButton objectId={objectId} group={group} />}
    </div>
  );
};

const RemoveGroupButton = ({ objectId, group }: ObjectGroupProps) => {
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
          graphqlClient.refetchQueries({ include: ["GET_GROUPS"] });
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
};
