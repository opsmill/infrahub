import { useState } from "react";

import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { getJsonPreview } from "@/shared/utils/json-preview";

import { ValueDialog } from "@/entities/nodes/object/ui/attribute-values/value-dialog";

const toJsonText = (value: unknown) => JSON.stringify(value, null, 2);

export interface JsonValueButtonProps {
  value: unknown;
  title: string;
  subtitle?: string;
  className?: string;
}

/** The start of a JSON value, which opens the whole value in a dialog. */
export function JsonValueButton({
  value,
  title,
  subtitle = "JSON",
  className,
}: JsonValueButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label={`View ${title} ${subtitle}`}
        className={classNames(
          "min-w-0 cursor-pointer truncate rounded text-left font-mono text-xs underline-offset-2 hover:underline",
          focusVisibleStyle,
          className
        )}
      >
        {getJsonPreview(value)}
      </button>

      {isOpen && (
        <ValueDialog
          title={title}
          subtitle={subtitle}
          copyLabel="Copy JSON"
          copyData={() => toJsonText(value)}
          onClose={() => setIsOpen(false)}
        >
          <div className="max-h-128 min-h-0 overflow-auto rounded-lg">
            <CodeViewer language="json" customStyle={{ margin: 0 }}>
              {toJsonText(value)}
            </CodeViewer>
          </div>
        </ValueDialog>
      )}
    </>
  );
}
