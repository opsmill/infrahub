import { Modal } from "@/shared/components/aria/modal";

import type { ModelSchema } from "@/entities/schema/types";
import { SchemaViewer } from "@/entities/schema/ui/schema-viewer";

interface SchemaViewerModalProps {
  schema: ModelSchema;
  defaultTab?: "properties" | "attributes" | "relationships";
}

export function SchemaViewerModal({ schema, defaultTab }: SchemaViewerModalProps) {
  return (
    <Modal className="w-[600px] max-w-[90vw]">
      {({ close }) => <SchemaViewer schema={schema} defaultTab={defaultTab} onClose={close} />}
    </Modal>
  );
}
