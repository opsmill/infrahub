import { Row } from "@/shared/components/container";

import type { ProtoPool } from "./data";
import { Joined, Namespace, Phrase } from "./row-parts";
import { getDefaultEntries, PoolHeader, PoolPage } from "./shared";

export function DotsVariant({ pool }: { pool: ProtoPool }) {
  return (
    <PoolPage
      pool={pool}
      header={
        <PoolHeader pool={pool}>
          <Row className="flex-wrap gap-x-2 gap-y-1 text-sm">
            <Joined>
              {[
                <Namespace key="ns" pool={pool} />,
                ...getDefaultEntries(pool).map((entry) => <Phrase key={entry.label} entry={entry} />),
              ]}
            </Joined>
          </Row>
        </PoolHeader>
      }
    />
  );
}
