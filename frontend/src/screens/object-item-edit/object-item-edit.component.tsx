import { gql, useQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { objectDetailsEdit } from "../../graphql/queries/objects/objectDetailsEdit";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/mutationDetailsFromFormData";
import updateObjectWithId from "../../utils/updateObjectWithId";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface Props {
  objectname: string;
  objectid: string;
  closeDrawer: Function;
  onUpdateComplete: Function;
}

export default function ObjectItemEditComponent(props: Props) {
  const { objectname, objectid, closeDrawer, onUpdateComplete } = props;
  const [schemaList] = useAtom(schemaState);
  const [genericsList] = useAtom(genericsState);
  const [schemaKindNameMap] = useAtom(schemaKindNameState);

  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const relationships = schema?.relationships?.filter(
    (relationship) => relationship.cardinality === "one"
  );

  const peers = (schema.relationships || []).map((r) => schemaKindNameMap[r.peer]).filter(Boolean);

  const queryString = schema
    ? objectDetailsEdit({
        ...schema,
        relationships,
        objectid,
        peers,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const { loading, error, data } = useQuery(
    gql`
      ${queryString}
    `,
    { skip: !schema }
  );

  if (error) {
    return <ErrorScreen />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (!data || (data && !data[schema.name])) {
    return <NoDataFound />;
  }

  const objectDetailsData = data[schema.name][0];

  const peerDropdownOptions = Object.entries(data).reduce((acc, [k, v]) => {
    if (peers.includes(k)) {
      return { ...acc, [k]: v };
    }

    return acc;
  }, {});

  const formStructure = getFormStructureForCreateEdit(
    schema,
    schemaList,
    genericsList,
    peerDropdownOptions,
    schemaKindNameMap,
    objectDetailsData
  );

  async function onSubmit(data: any) {
    const updateObject = getMutationDetailsFromFormData(schema, data, "update", objectDetailsData);

    if (Object.keys(updateObject).length) {
      try {
        await updateObjectWithId(objectid!, schema, updateObject);
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema.kind} updated`} />);
        closeDrawer();
        onUpdateComplete();
        return;
      } catch (e) {
        toast(
          <Alert
            message="Something went wrong while updating the object"
            type={ALERT_TYPES.ERROR}
          />
        );
        console.error("Something went wrong while updating the object", e);
        return;
      }
    }
  }

  return (
    <div className="bg-white flex-1 overflow-auto flex flex-col">
      {formStructure && (
        <EditFormHookComponent
          onCancel={props.closeDrawer}
          onSubmit={onSubmit}
          fields={formStructure}
        />
      )}
    </div>
  );
}
