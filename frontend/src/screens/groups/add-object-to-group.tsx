import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { GROUP_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { addRelationship } from "../../graphql/mutations/relationships/addRelationship";
import { removeRelationship } from "../../graphql/mutations/relationships/removeRelationship";
import { getGroups } from "../../graphql/queries/groups/getGroups";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, profilesAtom, schemaState } from "../../state/atoms/schema.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { getFormStructureForAddObjectToGroup } from "../../utils/formStructureForAddObjectToGroup";
import { stringifyWithoutQuotes } from "../../utils/string";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface Props {
  closeDrawer: Function;
  onUpdateComplete: Function;
}

export default function AddObjectToGroup(props: Props) {
  const { closeDrawer, onUpdateComplete } = props;

  const { objectname, objectid } = useParams();

  const allSchemas = useAtomValue(schemaState);
  const allGenerics = useAtomValue(genericsState);
  const allProfiles = useAtomValue(profilesAtom);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const schemaData = allGenerics.find((s) => s.kind === GROUP_OBJECT);

  const schema = allSchemas.find((s) => s.kind === objectname);
  const profile = allProfiles.find((s) => s.kind === objectname);
  const generic = allGenerics.filter((s) => s.name === objectname)[0];
  const objectSchemaData = schema || profile || generic;

  const queryString = schemaData
    ? getGroups({
        attributes: schemaData.attributes,
        kind: objectSchemaData.kind,
        groupKind: GROUP_OBJECT,
        objectid,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schemaData });

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the groups." />;
  }

  if (loading || !schemaData) {
    return <LoadingScreen />;
  }

  if (!data || (data && !data[schemaData.kind])) {
    return <NoDataFound message="No group found." />;
  }

  const groups = data[schemaData.kind]?.edges.map((edge: any) => edge.node);

  const objectGroups = data[objectSchemaData.kind]?.edges[0]?.node?.member_of_groups?.edges?.map(
    (edge: any) => edge.node
  );

  const formStructure = getFormStructureForAddObjectToGroup(groups, objectGroups);

  async function onSubmit(data: any) {
    // TODO: use object update mutation to provide the whole list
    setIsLoading(true);

    const { groupids } = data;

    const previousIds = objectGroups.map((group: any) => group.id);

    const newGroups = groupids.filter((id: string) => !previousIds.includes(id));
    const removedGroups = previousIds.filter((id: string) => !groupids.includes(id));

    try {
      if (newGroups.length) {
        const mutationString = addRelationship({
          data: stringifyWithoutQuotes({
            id: objectid,
            name: "member_of_groups",
            nodes: newGroups.map((id: string) => ({ id })),
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });
      }

      if (removedGroups.length) {
        const mutationString = removeRelationship({
          data: stringifyWithoutQuotes({
            id: objectid,
            name: "member_of_groups",
            nodes: removedGroups.map((id: string) => ({ id })),
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });
      }

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schemaData?.name} updated`} />);

      closeDrawer();

      onUpdateComplete();

      setIsLoading(false);

      return;
    } catch (e) {
      console.error("Something went wrong while updating the object:", e);

      setIsLoading(false);

      return;
    }
  }

  return (
    <div className="bg-custom-white flex-1 overflow-auto flex flex-col">
      {formStructure && (
        <EditFormHookComponent
          onCancel={closeDrawer}
          onSubmit={onSubmit}
          fields={formStructure}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}
