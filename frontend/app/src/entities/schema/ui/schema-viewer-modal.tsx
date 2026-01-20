import { Modal } from "@/shared/components/aria/modal";

import type { ModelSchema } from "@/entities/schema/types";
import { SchemaViewer } from "@/entities/schema/ui/schema-viewer";

interface SchemaViewerModalProps {
  schema: ModelSchema;
  defaultTab?: "properties" | "attributes" | "relationships";
  targetField?: string;
}

export function SchemaViewerModal({ schema, defaultTab, targetField }: SchemaViewerModalProps) {
  return (
    <Modal className="w-150">
      {({ close }) => (
        <SchemaViewer
          schema={schema}
          defaultTab={defaultTab}
          targetField={targetField}
          onClose={close}
          className="rounded-xl"
        />
      )}
    </Modal>
  );
}
