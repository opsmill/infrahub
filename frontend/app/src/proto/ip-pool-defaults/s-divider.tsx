import { Row } from "@/shared/components/container";

import type { ProtoPool } from "./data";
import { Divider, Joined, Namespace, Phrase } from "./row-parts";
import { getDefaultEntries, PoolHeader, PoolPage } from "./shared";

export function DividerVariant({ pool }: { pool: ProtoPool }) {
  return (
    <PoolPage
      pool={pool}
      header={
        <PoolHeader pool={pool}>
          <Row className="flex-wrap gap-x-2 gap-y-1 text-sm">
            <Namespace pool={pool} />
            <Divider />
            <Joined>
              {getDefaultEntries(pool).map((entry) => (
                <Phrase key={entry.label} entry={entry} />
              ))}
            </Joined>
          </Row>
        </PoolHeader>
      }
    />
  );
}
