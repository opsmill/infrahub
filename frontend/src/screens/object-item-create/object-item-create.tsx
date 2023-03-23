import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import createObject from "../../utility/createObject";
import getDropdownOptionsForRelatedPeers from "../../utility/dropdownOptionsForRelatedPeers";
import getFormStructureForCreateEdit from "../../utility/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utility/mutationDetailsFromFormData";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";

export default function ObjectItemCreate() {
  let { objectname } = useParams();
  const [schemaList] = useAtom(schemaState);
  const [schemaKindNameMap] = useAtom(schemaKindNameState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const [formStructure, setFormStructure] = useState<DynamicFieldData[]>();

  const navigate = useNavigate();

  const initForm = useCallback(async () => {
    const peers = (schema.relationships || []).map((r) => schemaKindNameMap[r.peer]);
    const peerDropdownOptions = await getDropdownOptionsForRelatedPeers(peers);
    const formStructure = getFormStructureForCreateEdit(schema, peerDropdownOptions, schemaKindNameMap);
    setFormStructure(formStructure);
  }, [schema, schemaKindNameMap]);

  useEffect(() => {
    if(schema) {
      initForm();
    }
  }, [schema, initForm]);

  async function onSubmit(data: any, error: any) {
    const mutationArgs = getMutationDetailsFromFormData(schema, data, "create");
    if (mutationArgs.length) {
      try {
        await createObject(schema, mutationArgs);
      } catch {
        console.error("Something went wrong while updating the object");
      }
      navigate(-1);
    } else {
      console.info("Nothing to update");
    }
  }

  return (
    <div className="p-4 flex-1 overflow-auto flex">
      {schema && formStructure && (
        <div className="flex-1">
          <EditFormHookComponent onSubmit={onSubmit} fields={formStructure} />
        </div>
      )}
    </div>
  )

}
