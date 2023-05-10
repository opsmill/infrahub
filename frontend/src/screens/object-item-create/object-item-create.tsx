import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { genericSchemaState, genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import createObject from "../../utils/createObject";
import getDropdownOptionsForRelatedPeers from "../../utils/dropdownOptionsForRelatedPeers";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/mutationDetailsFromFormData";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";

interface iProps {
  objectname: string;
  onCancel?: Function;
  onCreate: Function;
}

export default function ObjectItemCreate(props: iProps) {
  let { objectname } = props;
  const [schemaList] = useAtom(schemaState);
  const [genericsList] = useAtom(genericsState);
  const [genericSchemaMap] = useAtom(genericSchemaState);
  const [schemaKindNameMap] = useAtom(schemaKindNameState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const [formStructure, setFormStructure] = useState<DynamicFieldData[]>();

  const initForm = useCallback(async () => {
    const peers = (schema.relationships || []).map((r) => schemaKindNameMap[r.peer]);
    const peerDropdownOptions = await getDropdownOptionsForRelatedPeers(peers);
    const formStructure = getFormStructureForCreateEdit(
      schema,
      schemaList,
      genericsList,
      peerDropdownOptions,
      schemaKindNameMap,
      genericSchemaMap
    );
    setFormStructure(formStructure);
  }, [genericSchemaMap, genericsList, schema, schemaKindNameMap, schemaList]);

  useEffect(() => {
    if (schema) {
      initForm();
    }
  }, [schema, initForm]);

  async function onSubmit(data: any) {
    const newObject = getMutationDetailsFromFormData(schema, data, "create");
    if (Object.keys(newObject).length) {
      try {
        await createObject(schema, newObject);
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema.kind} created`} />);
        if (props.onCreate) {
          props.onCreate();
        }
      } catch (err: any) {
        console.error("Something went wrong while creating the object: ", err);
        toast(
          <Alert type={ALERT_TYPES.ERROR} message={"An error occured"} details={err.message} />
        );
      }
    } else {
      console.info("Nothing to create");
    }
  }

  return (
    <div className="bg-white flex-1 overflow-auto flex">
      {schema && formStructure && (
        <div className="flex-1">
          <EditFormHookComponent
            onSubmit={onSubmit}
            onCancel={() => (props.onCancel ? props.onCancel() : null)}
            fields={formStructure}
          />
        </div>
      )}
    </div>
  );
}
