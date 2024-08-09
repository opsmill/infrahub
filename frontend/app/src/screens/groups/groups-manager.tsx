import { SearchInput } from "@/components/ui/search-input";
import { useState } from "react";
import { IModelSchema } from "@/state/atoms/schema.atom";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import { getGroupsQuery } from "@/graphql/queries/groups/getGroups";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import ErrorScreen from "@/screens/errors/error-screen";
import ObjectGroupsList from "@/screens/groups/object-groups-list";
import AddGroupTriggerButton from "@/screens/groups/add-group-trigger-button";
import { classNames } from "@/utils/common";
import { GroupDataFromAPI } from "@/screens/groups/types";

export type GroupsManagerProps = {
  className?: string;
  schema: IModelSchema;
  objectId: string;
  onUpdateCompleted?: () => void;
};

export const GroupsManager = ({ className, schema, objectId }: GroupsManagerProps) => {
  const [query, setQuery] = useState("");

  const { loading, error, data } = useQuery(
    gql(
      getGroupsQuery({
        objectKind: schema.kind,
        objectId,
      })
    )
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

  const currentObjectGroups: Array<GroupDataFromAPI> =
    currentObjectData.member_of_groups?.edges?.map(({ node }: { node: GroupDataFromAPI }) => node);

  const filteredVisibleGroups =
    query === ""
      ? currentObjectGroups
      : currentObjectGroups.filter((group) =>
          group.display_label.toLowerCase().includes(query.toLowerCase())
        );

  return (
    <div className={classNames("h-full flex flex-col gap-4", className)}>
      <div className="flex gap-2">
        <SearchInput
          containerClassName="flex-grow"
          className="h-9"
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
