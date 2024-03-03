import { useAtom } from "jotai";
import { useState } from "react";
import { useTitle } from "../../hooks/useTitle";
import { ModelSchema, schemaState } from "../../state/atoms/schema.atom";
import { SchemaSelector } from "./schema-selector";
import { SchemaPageHeader } from "./schema-page-header";
import { Badge } from "../../components/ui/badge";

export default function SchemaPage() {
  useTitle("Schema");
  const [schema] = useAtom(schemaState);
  const [selectedSchema, setSelectedSchema] = useState<ModelSchema>();

  return (
    <>
      <SchemaPageHeader
        title={
          <>
            Schema Visualizer <Badge>{schema.length}</Badge>
          </>
        }
      />

      <div className="p-2 flex gap-2 items-start">
        <SchemaSelector
          className="flex-grow"
          selectedSchema={selectedSchema}
          onClick={setSelectedSchema}
        />
        {/*{selectedSchema && <SchemaViewer schema={selectedSchema} />}*/}
      </div>
    </>
  );
}
