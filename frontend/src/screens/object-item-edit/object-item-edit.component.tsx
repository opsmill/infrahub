import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import getObjectDetails from "../../graphql/queries/objects/objectDetails";
import { branchState } from "../../state/atoms/branch.atom";
import { genericSchemaState, genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { timeState } from "../../state/atoms/time.atom";
import getDropdownOptionsForRelatedPeers from "../../utils/dropdownOptionsForRelatedPeers";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/mutationDetailsFromFormData";
import updateObjectWithId from "../../utils/updateObjectWithId";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
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
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);
  const [schemaKindNameMap] = useAtom(schemaKindNameState);
  const [formStructure, setFormStructure] = useState<DynamicFieldData[]>();
  // const navigate = useNavigate();

  const [objectDetails, setObjectDetails] = useState<any | undefined>();
  const [schemaList] = useAtom(schemaState);
  const [genericsList] = useAtom(genericsState);
  const [genericSchemaMap] = useAtom(genericSchemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const initForm = useCallback(
    async (row: any) => {
      const peers = (schema.relationships || []).map((r) => schemaKindNameMap[r.peer]);
      const peerDropdownOptions = await getDropdownOptionsForRelatedPeers(peers);
      const formStructure = getFormStructureForCreateEdit(
        schema,
        schemaList,
        genericsList,
        peerDropdownOptions,
        schemaKindNameMap,
        genericSchemaMap,
        row
      );
      setFormStructure(formStructure);
    },
    [genericSchemaMap, genericsList, schema, schemaKindNameMap, schemaList]
  );

  const fetchItemDetails = useCallback(async () => {
    setHasError(false);
    setIsLoading(true);
    setObjectDetails(undefined);
    try {
      const data = await getObjectDetails(schema, objectid!);
      setObjectDetails(data);
      initForm(data);
    } catch (err) {
      setHasError(true);
    }
    setIsLoading(false);
  }, [initForm, objectid, schema]);

  useEffect(() => {
    if (schema) {
      fetchItemDetails();
    }
  }, [objectname, objectid, schemaList, date, branch, schema, fetchItemDetails]);

  if (hasError) {
    return <ErrorScreen />;
  }

  if (isLoading || !schema) {
    return <LoadingScreen />;
  }

  if (!objectDetails) {
    return <NoDataFound />;
  }

  async function onSubmit(data: any) {
    const updateObject = getMutationDetailsFromFormData(schema, data, "update", objectDetails);

    if (Object.keys(updateObject).length) {
      try {
        await updateObjectWithId(objectid!, schema, updateObject);
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema.kind} updated`} />);
        closeDrawer();
        onUpdateComplete();
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
