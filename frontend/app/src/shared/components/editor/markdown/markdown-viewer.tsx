import { Button } from "@infrahub/ui";
import { useState } from "react";

import { Col, Row } from "@/shared/components/container";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
<<<<<<< HEAD
=======
import { classNames } from "@/shared/utils/common";
>>>>>>> origin/stable

import { MarkdownRender } from "./markdown-render";

export function MarkdownViewer({ children }: { children: string }) {
  const [displayRaw, setDisplayRaw] = useState(false);

  return (
<<<<<<< HEAD
    <Col>
      <Row>
        <Button variant="outline" onPress={() => setDisplayRaw(false)}>
          Preview
        </Button>

        <Button variant="outline" onPress={() => setDisplayRaw(true)}>
          Code
=======
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button
          variant={"ghost"}
          className={classNames(
            "rounded-none border-custom-blue-700 border-b",
            displayRaw ? "border-0" : ""
          )}
          onPress={() => setDisplayRaw(false)}
        >
          View
        </Button>

        <Button
          variant={"ghost"}
          className={classNames(
            "rounded-none border-custom-blue-700 border-b",
            displayRaw ? "" : "border-0"
          )}
          onPress={() => setDisplayRaw(true)}
        >
          Raw
>>>>>>> origin/stable
        </Button>
      </Row>

      {displayRaw ? (
        <CodeViewer language="markdown">{children}</CodeViewer>
      ) : (
        <MarkdownRender markdownText={children} />
      )}
    </Col>
  );
}
