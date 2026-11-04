import type React from "react";
import { Button as AriaButton, DialogTrigger } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { SchemaViewerModal } from "@/entities/schema/ui/schema-viewer-modal";

export const schemaLinkStyle =
  "font-medium underline decoration-dotted data-hovered:decoration-solid";

export interface SchemaReferenceProps {
  schema: ModelSchema | null;
  targetField?: string;
  className?: string;
  children: React.ReactNode;
}

export function SchemaReference({
  schema,
  targetField,
  className,
  children,
}: SchemaReferenceProps) {
  if (!schema) return <span className={classNames(className, "no-underline")}>{children}</span>;

  const isRelationship = schema.relationships?.some((field) => field.name === targetField);
  const fieldTab = isRelationship ? "relationships" : "attributes";
  const defaultTab = targetField ? fieldTab : undefined;

  return (
    <DialogTrigger>
      <AriaButton
        className={classNames(
          "cursor-pointer rounded-md outline-none data-focus-visible:ring-2 data-focus-visible:ring-ring-halo",
          className
        )}
      >
        {children}
      </AriaButton>
      <SchemaViewerModal schema={schema} defaultTab={defaultTab} targetField={targetField} />
    </DialogTrigger>
  );
}
