import { Modal, type ModalProps } from "@/shared/components/aria/modal";
import { classNames } from "@/shared/utils/common";

import type { ModelSchema } from "@/entities/schema/types";
import { SchemaViewer } from "@/entities/schema/ui/schema-viewer";

interface SchemaViewerModalProps extends Omit<ModalProps, "children"> {
  schema: ModelSchema;
  defaultTab?: "properties" | "attributes" | "relationships";
  targetField?: string;
}

export function SchemaViewerModal({
  schema,
  defaultTab,
  targetField,
  className,
  ...props
}: SchemaViewerModalProps) {
  return (
    <Modal aria-label="Schema viewer" className={classNames("w-150", className)} {...props}>
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
