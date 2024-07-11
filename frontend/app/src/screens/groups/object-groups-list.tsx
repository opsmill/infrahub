import ItemGroup from "@/components/ui/item-group";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { Button } from "@/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { QSP } from "@/config/qsp";
import ModalDelete from "@/components/modals/modal-delete";
import { useState } from "react";
import { useMutation } from "@apollo/client";
import { REMOVE_GROUP } from "@/graphql/mutations/groups/removeGroup";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { pluralize } from "@/utils/string";

export type ObjectGroup = {
  id: string;
  display_label: string;
  description: { value: string } | null;
  members: {
    count: number;
  };
  __typename: string;
};

type ObjectGroupsListProps = {
  className?: string;
  objectId?: string;
  groups: Array<ObjectGroup>;
};

export default function ObjectGroupsList({ className, objectId, groups }: ObjectGroupsListProps) {
  if (groups.length === 0) {
    return <p className="py-4 text-center">There are no groups to display.</p>;
  }

  return (
    <ItemGroup className={className}>
      {groups.map((group) => (
        <ObjectGroupItem objectId={objectId} key={group.id} group={group} />
      ))}
    </ItemGroup>
  );
}

type ObjectGroupProps = {
  objectId?: string;
  group: ObjectGroup;
};

const ObjectGroupItem = ({ objectId, group }: ObjectGroupProps) => {
  return (
    <div className="flex justify-between gap-2 px-2 py-4">
      <div className="overflow-hidden space-y-1">
        <Link
          to={getObjectDetailsUrl2(group.__typename, group.id)}
          className="font-semibold hover:underline truncate block">
          {group.display_label}
        </Link>

        <div className="flex items-center gap-2">
          <Link
            to={getObjectDetailsUrl2(group.__typename, group.id, [
              { name: QSP.TAB, value: "members" },
            ])}
            className="text-sm font-light hover:underline">
            {pluralize(group.members.count, "member")}
          </Link>

          <Link to={getObjectDetailsUrl2(group.__typename)}>
            <Badge variant="blue" className="hover:underline">
              {group.__typename}
            </Badge>
          </Link>
        </div>

        {group.description && <p className="text-sm">{group.description.value}</p>}
      </div>

      {objectId && <RemoveGroupButton objectId={objectId} group={group} />}
    </div>
  );
};

const RemoveGroupButton = ({ objectId, group }: ObjectGroupProps) => {
  const [removeGroup, { loading }] = useMutation(REMOVE_GROUP, {
    onCompleted: () => graphqlClient.refetchQueries({ include: ["GET_GROUPS"] }),
  });
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  return (
    <>
      <Tooltip content="Leave" enabled>
        <Button
          variant="ghost"
          size="icon"
          className="flex-shrink-0"
          onClick={() => setShowDeleteModal(true)}
          data-testid="leave-group-button">
          <Icon icon="mdi:link-variant-remove" className="text-lg text-red-600" />
        </Button>
      </Tooltip>

      <ModalDelete
        title="Leave Group"
        description={`Are you sure you want to leave group ${group.display_label}?`}
        onCancel={() => setShowDeleteModal(false)}
        onDelete={() => removeGroup({ variables: { objectId, groupId: group.id } })}
        open={showDeleteModal}
        setOpen={() => setShowDeleteModal(false)}
        isLoading={loading}
      />
    </>
  );
};
