import { SearchInput } from "@/components/ui/search-input";
import { useState } from "react";
import { genericsState, IModelSchema } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import { getGroups } from "@/graphql/queries/groups/getGroups";
import { GROUP_OBJECT } from "@/config/constants";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import ErrorScreen from "@/screens/errors/error-screen";
import ObjectGroupsList, { ObjectGroup } from "@/screens/groups/object-groups-list";
import AddGroupTriggerButton from "@/screens/groups/add-group-trigger-button";

export type GroupsManagerProps = {
  schema: IModelSchema;
  objectId: string;
  onUpdateCompleted?: () => void;
};

export const GroupsManager = ({ schema, objectId }: GroupsManagerProps) => {
  const generics = useAtomValue(genericsState);
  const coreGroupSchema = generics.find((s) => s.kind === GROUP_OBJECT);
  const [query, setQuery] = useState("");

  const { loading, error, data } = useQuery(
    gql(
      getGroups({
        attributes: coreGroupSchema?.attributes,
        kind: schema.kind,
        groupKind: GROUP_OBJECT,
        objectid: objectId,
      })
    ),
    { skip: !coreGroupSchema }
  );

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const currentObjectData = data[schema.kind!]?.edges[0]?.node;

  if (!currentObjectData) {
    return (
      <NoDataFound
        message={
          <div>
            <div className="text-center mb-4">No data found.</div>
            <div className="text-sm">
              <span className="font-semibold">Kind</span>: {schema.kind}
            </div>
            <div className="text-sm">
              <span className="font-semibold">Id</span>: {objectId}
            </div>
          </div>
        }
      />
    );
  }

  const currentObjectGroups: Array<ObjectGroup> = currentObjectData.member_of_groups?.edges?.map(
    ({ node }: { node: ObjectGroup }) => node
  );

  const filteredVisibleGroups =
    query === ""
      ? currentObjectGroups
      : currentObjectGroups.filter((group) =>
          group.display_label.toLowerCase().includes(query.toLowerCase())
        );

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="flex gap-2 h-10">
        <SearchInput
          containerClassName="flex-grow"
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter groups..."
        />

        <AddGroupTriggerButton schema={schema} objectId={objectId} />
      </div>

      <ObjectGroupsList
        objectId={objectId}
        groups={filteredVisibleGroups}
        className="flex-grow overflow-auto"
      />
    </div>
  );
};
