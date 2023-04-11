import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { branchState } from "../../state/atoms/branch.atom";
import { genericSchemaState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { timeState } from "../../state/atoms/time.atom";
import getDropdownOptionsForRelatedPeers from "../../utils/dropdownOptionsForRelatedPeers";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/mutationDetailsFromFormData";
import getObjectDetails from "../../graphql/queries/objects/objectDetails";
import updateObjectWithId from "../../utils/updateObjectWithId";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

export default function ObjectItemEdit() {
  let { objectname, objectid } = useParams();
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);
  const [schemaKindNameMap] = useAtom(schemaKindNameState);
  const [formStructure, setFormStructure] = useState<DynamicFieldData[]>();
  const navigate = useNavigate();

  const [objectDetails, setObjectDetails] = useState<any | undefined>();
  const [schemaList] = useAtom(schemaState);
  const [genericSchemaMap] = useAtom(genericSchemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const initForm = useCallback(async (row: any) => {
    const peers = (schema.relationships || []).map((r) => schemaKindNameMap[r.peer]);
    const peerDropdownOptions = await getDropdownOptionsForRelatedPeers(peers);
    const formStructure = getFormStructureForCreateEdit(schema, peerDropdownOptions, schemaKindNameMap, genericSchemaMap, row);
    setFormStructure(formStructure);
  }, [genericSchemaMap, schema, schemaKindNameMap]);

  const fetchItemDetails = useCallback(async () => {
    setHasError(false);
    setIsLoading(true);
    setObjectDetails(undefined);
    try {
      const data = await getObjectDetails(schema, objectid!);
      setObjectDetails(data);
      initForm(data);
    } catch(err) {
      setHasError(true);
    }
    setIsLoading(false);
  }, [initForm, objectid, schema]);

  useEffect(() => {
    if(schema) {
      fetchItemDetails();
    }
  }, [objectname, objectid, schemaList, schema, date, branch, fetchItemDetails]);

  if (hasError) {
    return <ErrorScreen />;
  }

  if (isLoading || !schema) {
    return <LoadingScreen />;
  }

  if (!objectDetails) {
    return <NoDataFound />;
  }

  async function onSubmit(data: any, error: any) {
    const updateObject = getMutationDetailsFromFormData(schema, data, "update", objectDetails);
    if (Object.keys(updateObject).length) {
      try {
        await updateObjectWithId(objectid!, schema, updateObject);
      } catch {
        console.error("Something went wrong while updating the object");
      }
      navigate(-1);
    } else {
      console.info("Nothing to update");
    }
  }

  return (
    <div className="p-4 bg-white flex-1 overflow-auto flex">
      {formStructure && (
        <div className="flex-1">
          <EditFormHookComponent onSubmit={onSubmit} fields={formStructure} />
        </div>
      )}
    </div>
  );
}
