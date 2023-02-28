import { useAtom } from "jotai";
import { useState } from "react";
import { classNames } from "../../App";
import { NodeSchema } from "../../generated/graphql";
import { schemaState } from "../../state/atoms/schema.atom";
import ObjectRows from "./object-rows";

export default function OpsObjects() {
  const [schema] = useAtom(schemaState);
  const [selectedSchema, setSelectedSchema] = useState<any>();
  return (
    <div className="flex overflow-auto">
      <div className="flex-1 overflow-auto">
        <div className="p-4 space-y-4 bg-gray-50">
          {schema.map((schema) => {
            return (
              <div
                key={schema?.name}
                className={classNames(
                  "p-4 shadow-lg border border-gray-200 bg-white rounded-md hover:bg-gray-100 cursor-pointer",
                  selectedSchema?.name === schema.name ? "border-indigo-500" : ""
                )}
                onClick={() => {
                  setSelectedSchema(schema);
                }}
              >
                {schema?.kind} - {schema?.name}
                <div className="text-sm text-gray-600">
                  {schema?.attributes?.length} attribute(s),{" "}
                  {schema?.relationships?.length} relationships(s)
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {selectedSchema && <ObjectRows schema={selectedSchema} />}
      </div>
    </div>
  );
}
