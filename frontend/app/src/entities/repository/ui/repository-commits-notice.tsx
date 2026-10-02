import type { ReactNode } from "react";

import { Row } from "@/shared/components/container";

export function RepositoryCommitsNotice({ children }: { children: ReactNode }) {
  return (
    <Row className="items-center justify-center gap-2 p-2 text-foreground-muted text-sm">
      {children}
    </Row>
  );
}
