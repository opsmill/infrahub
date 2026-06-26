import { Modal, type ModalProps } from "@infrahub/ui";
import { useState } from "react";

import { classNames } from "@/shared/utils/common";

import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
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
  const [nestedKind, setNestedKind] = useState<string | null>(null);

  return (
    <Modal aria-label="Schema viewer" className={classNames("w-150 p-0", className)} {...props}>
      {({ close }) => (
        <>
          <SchemaViewer
            schema={schema}
            defaultTab={defaultTab}
            targetField={targetField}
            onKindClick={setNestedKind}
            onClose={close}
            className="rounded-[inherit] border-0 p-3"
          />

          {nestedKind && (
            <NestedSchemaViewerModal
              kind={nestedKind}
              onOpenChange={(isOpen) => {
                if (!isOpen) setNestedKind(null);
              }}
            />
          )}
        </>
      )}
    </Modal>
  );
}

function NestedSchemaViewerModal({
  kind,
  onOpenChange,
}: {
  kind: string;
  onOpenChange: (isOpen: boolean) => void;
}) {
  const { schema } = useSchema(kind);

  if (!schema) return null;

  return <SchemaViewerModal schema={schema} isOpen onOpenChange={onOpenChange} />;
}
