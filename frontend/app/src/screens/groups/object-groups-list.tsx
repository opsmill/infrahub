import { Button } from "@/components/buttons/button-primitive";
import ItemGroup from "@/components/layouts/item-group";
import ModalDelete from "@/components/modals/modal-delete";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { QSP } from "@/config/qsp";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { REMOVE_RELATIONSHIP } from "@/graphql/mutations/relationships/removeRelationship";
import { useMutation } from "@/hooks/useQuery";
import { GroupDataFromAPI } from "@/screens/groups/types";
import { schemaState } from "@/state/atoms/schema.atom";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { pluralize } from "@/utils/string";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { Link } from "react-router-dom";

type ObjectGroupsListProps = {
  className?: string;
  objectId?: string;
  groups: Array<GroupDataFromAPI>;
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
  group: GroupDataFromAPI;
};

const ObjectGroupItem = ({ objectId, group }: ObjectGroupProps) => {
  const nodes = useAtomValue(schemaState);
  const groupSchema = nodes.find((node) => node.kind === group.__typename);

  return (
    <div className="flex justify-between items-center gap-4 p-2 bg-gray-100 rounded-md border border-gray-300 relative">
      <div className="overflow-hidden space-y-1">
        <Link
          to={getObjectDetailsUrl2(group.__typename, group.id)}
          className="font-semibold hover:underline truncate block"
        >
          {group.display_label}
        </Link>

        <div className="flex items-center gap-2">
          <Link
            to={getObjectDetailsUrl2(group.__typename, group.id, [
              { name: QSP.TAB, value: "members" },
            ])}
            className="text-sm font-light hover:underline"
          >
            {pluralize(group.members.count, "member")}
          </Link>

          <Link to={getObjectDetailsUrl2(group.__typename)}>
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
  const [removeGroup, { loading }] = useMutation(REMOVE_RELATIONSHIP, {
    variables: { relationshipName: "member_of_groups" },
    onCompleted: () => graphqlClient.refetchQueries({ include: ["GET_GROUPS"] }),
  });
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  return (
    <>
      <Tooltip content="Leave" enabled>
        <Button
          variant="ghost"
          size="icon"
          className="flex-shrink-0 hover:bg-gray-200"
          onClick={() => setShowDeleteModal(true)}
          data-testid="leave-group-button"
        >
          <Icon icon="mdi:link-variant-remove" className="text-lg text-red-600" />
        </Button>
      </Tooltip>

      <ModalDelete
        title="Leave Group"
        description={`Are you sure you want to leave group ${group.display_label}?`}
        onCancel={() => setShowDeleteModal(false)}
        onDelete={() =>
          removeGroup({ variables: { objectId, relationshipIds: [{ id: group.id }] } })
        }
        open={showDeleteModal}
        setOpen={() => setShowDeleteModal(false)}
        isLoading={loading}
      />
    </>
  );
};
