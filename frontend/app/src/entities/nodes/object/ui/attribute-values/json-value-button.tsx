import { Button } from "@infrahub/ui";
import React from "react";

import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { classNames } from "@/shared/utils/common";
import { getJsonPreview } from "@/shared/utils/json-preview";

import { ValueDialog } from "@/entities/nodes/object/ui/attribute-values/value-dialog";

const toJsonText = (value: unknown) => JSON.stringify(value, null, 2);

function JsonCode({ value }: { value: unknown }) {
  return (
    <div className="max-h-128 min-h-0 overflow-auto rounded-lg">
      <CodeViewer language="json" customStyle={{ margin: 0 }}>
        {toJsonText(value)}
      </CodeViewer>
    </div>
  );
}

export interface JsonValueButtonProps {
  value: unknown;
  attributeLabel: string;
  subtitle?: string;
  className?: string;
}

export function JsonValueButton({
  value,
  attributeLabel,
  subtitle = "JSON",
  className,
}: JsonValueButtonProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="xxs"
        onPress={() => setIsOpen(true)}
        aria-label={`View ${attributeLabel} ${subtitle}`}
        className={classNames(
          "min-w-0 max-w-full justify-start font-mono font-normal hover:underline",
          className
        )}
      >
        <span className="truncate">{getJsonPreview(value)}</span>
      </Button>

      <ValueDialog
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        title={attributeLabel}
        subtitle={subtitle}
        copyLabel="Copy JSON"
        copyData={() => toJsonText(value)}
      >
        <JsonCode value={value} />
      </ValueDialog>
    </>
  );
}
