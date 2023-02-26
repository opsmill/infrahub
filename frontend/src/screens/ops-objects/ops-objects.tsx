import { useAtom } from "jotai";
import { useState } from "react";
import { classNames } from "../../App";
import { NodeSchema } from "../../generated/graphql";
import { schemaState } from "../../state/atoms/schema.atom";
import ObjectRows from "./object-rows";

export default function OpsObjects() {
  const [schema] = useAtom(schemaState);
  const [selectedSchema, setSelectedSchema] = useState<NodeSchema>();
  
  return (
    <div className="flex overflow-auto">
      <div className="flex-1 overflow-auto">
        <div className="p-4 space-y-4 bg-gray-50">
          {schema.map((schema) => (
            <div
              key={schema?.name.value}
              className={classNames(
                "p-4 shadow-lg border border-gray-200 bg-white rounded-md hover:bg-gray-100 cursor-pointer",
                selectedSchema?.name.value === schema?.name.value
                  ? "border-blue-500"
                  : ""
              )}
              onClick={() => {
                if (schema) {
                  setSelectedSchema(schema);
                }
              }}
            >
              {schema?.kind.value} - {schema?.name.value}
              <div>{schema?.attributes?.length} attribute(s)</div>
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {selectedSchema && <ObjectRows schema={selectedSchema} />}
      </div>
    </div>
  );
}
