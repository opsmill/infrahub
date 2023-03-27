import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import createObject from "../../utils/createObject";
import getDropdownOptionsForRelatedPeers from "../../utils/dropdownOptionsForRelatedPeers";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/mutationDetailsFromFormData";
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
    const newObject = getMutationDetailsFromFormData(schema, data, "create");
    if (Object.keys(newObject).length) {
      try {
        await createObject(schema, newObject);
      } catch(err) {
        console.error("Something went wrong while creating the object: ", err);
      }
      navigate(-1);
    } else {
      console.info("Nothing to create");
    }
  }

  return (
    <div className="p-4 bg-white flex-1 overflow-auto flex">
      {schema && formStructure && (
        <div className="flex-1">
          <EditFormHookComponent onSubmit={onSubmit} fields={formStructure} />
        </div>
      )}
    </div>
  )

}
