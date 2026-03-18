import { useState } from "react";

import { classNames } from "@/shared/utils/common";

import { Button } from "../../ui/button";
import { CodeViewer } from "../code/code-viewer";
import { MarkdownRender } from "./markdown-render";

export function MarkdownViewer({ children }: { children: string }) {
  const [displayRaw, setDisplayRaw] = useState(false);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button
          variant={"ghost"}
          className={classNames(
            "rounded-none border-custom-blue-700 border-b",
            displayRaw ? "border-0" : ""
          )}
          onClick={() => setDisplayRaw(false)}
        >
          View
        </Button>

        <Button
          variant={"ghost"}
          className={classNames(
            "rounded-none border-custom-blue-700 border-b",
            displayRaw ? "" : "border-0"
          )}
          onClick={() => setDisplayRaw(true)}
        >
          Raw
        </Button>
      </div>

      {displayRaw ? (
        <CodeViewer language="markdown">{children}</CodeViewer>
      ) : (
        <MarkdownRender markdownText={children} />
      )}
    </div>
  );
}
