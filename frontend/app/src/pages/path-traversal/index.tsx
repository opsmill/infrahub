import Content from "@/shared/components/layout/content";

import { PathTraversalPage } from "@/entities/path-traversal/ui/path-traversal-page";

export function Component() {
  return (
    <Content.Card className="grow">
      <PathTraversalPage />
    </Content.Card>
  );
}
