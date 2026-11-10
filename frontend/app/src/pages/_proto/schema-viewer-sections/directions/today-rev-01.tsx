// PROTOTYPE design-jam schema-viewer-sections
import { SchemaViewer } from "@/entities/schema/ui/schema-viewer";

import { SchemaPage } from "../context";

export function TodayRev01() {
  return (
    <SchemaPage>
      {(schema, onKindClick) => (
        <SchemaViewer
          key={schema.kind}
          className="w-full"
          schema={schema}
          onKindClick={onKindClick}
          onClose={() => {}}
        />
      )}
    </SchemaPage>
  );
}
