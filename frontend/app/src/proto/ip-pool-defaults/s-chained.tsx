import React from "react";

import { Row } from "@/shared/components/container";

import type { ProtoPool } from "./data";
import { Divider, Namespace, Phrase } from "./row-parts";
import { getDefaultEntries, PoolHeader, PoolPage } from "./shared";

export function ChainedVariant({ pool }: { pool: ProtoPool }) {
  const entries = getDefaultEntries(pool);

  return (
    <PoolPage
      pool={pool}
      header={
        <PoolHeader pool={pool}>
          <Row className="flex-wrap gap-x-2 gap-y-1 text-sm">
            <Namespace pool={pool} />
            <Divider />
            <span>
              {entries.map((entry, index) => (
                <React.Fragment key={entry.label}>
                  {index > 0 && <span className="text-foreground-muted">, </span>}
                  <Phrase
                    entry={entry}
                    lowercase={index > 0}
                    short={index > 0 && entries[index - 1]?.value !== null && entry.value !== null}
                  />
                </React.Fragment>
              ))}
            </span>
          </Row>
        </PoolHeader>
      }
    />
  );
}
