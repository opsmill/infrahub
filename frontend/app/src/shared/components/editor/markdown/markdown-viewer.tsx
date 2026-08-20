import { Button } from "@infrahub/ui";
import { useState } from "react";

import { Col, Row } from "@/shared/components/container";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";

import { MarkdownRender } from "./markdown-render";

export function MarkdownViewer({ children }: { children: string }) {
  const [displayRaw, setDisplayRaw] = useState(false);

  return (
    <Col>
      <Row>
        <Button variant="outline" onPress={() => setDisplayRaw(false)}>
          Preview
        </Button>

        <Button variant="outline" onPress={() => setDisplayRaw(true)}>
          Code
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
