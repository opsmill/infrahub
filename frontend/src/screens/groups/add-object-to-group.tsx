import { gql, useReactiveVar } from "@apollo/client";
import { useAtom } from "jotai";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { GROUP_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { addRelationship } from "../../graphql/mutations/relationships/addRelationship";
import { getGroups } from "../../graphql/queries/groups/getGroups";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import usePagination from "../../hooks/usePagination";
import useQuery from "../../hooks/useQuery";
import { genericsState } from "../../state/atoms/schema.atom";
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

  const { objectid } = useParams();

  const [genericsList] = useAtom(genericsState);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [pagination] = usePagination();
  const [isLoading, setIsLoading] = useState(false);

  const schemaData = genericsList.filter((s) => s.name === GROUP_OBJECT)[0];

  const filtersString = [
    // Add pagination filters
    ...[
      { name: "offset", value: pagination?.offset },
      { name: "limit", value: pagination?.limit },
    ].map((row: any) => `${row.name}: ${row.value}`),
  ].join(",");

  const queryString = schemaData
    ? getGroups({
        attributes: schemaData.attributes,
        filters: filtersString,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  console.log("queryString: ", queryString);
  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schemaData });

  if (error) {
    console.error("An error occured while retrieving the object details: ", error);

    toast(
      <Alert
        message="An error occured while retrieving the object details"
        type={ALERT_TYPES.ERROR}
      />
    );

    return <ErrorScreen />;
  }

  if (loading || !schemaData) {
    return <LoadingScreen />;
  }

  if (!data || (data && !data[schemaData.kind])) {
    return <NoDataFound />;
  }

  const groups = data[schemaData.kind]?.edges.map((edge: any) => edge.node);
  console.log("groups: ", groups);

  const formStructure = getFormStructureForAddObjectToGroup(groups);
  console.log("formStructure: ", formStructure);

  async function onSubmit(data: any) {
    const { groupids } = data;

    try {
      const mutationString = addRelationship({
        data: stringifyWithoutQuotes({
          id: objectid,
          name: "member_of_groups",
          nodes: groupids.map((option: any) => ({ id: option.id })),
        }),
      });

      console.log("mutationString: ", mutationString);

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schemaData.name} updated`} />);

      closeDrawer();

      onUpdateComplete();

      setIsLoading(false);

      return;
    } catch (e) {
      setIsLoading(false);

      toast(
        <Alert message="Something went wrong while updating the object" type={ALERT_TYPES.ERROR} />
      );
      console.error("Something went wrong while updating the object:", e);
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
