import { Row } from "@/shared/components/container";

import type { ProtoPool } from "./data";
import { Divider, Joined, Phrase } from "./row-parts";
import { getDefaultEntries, PoolHeader, PoolPage } from "./shared";
import { Link } from "@/shared/components/ui/link";

export function NoWrapVariant({ pool }: { pool: ProtoPool }) {
  return (
    <PoolPage
      pool={pool}
      header={
        <PoolHeader pool={pool}>
          <Row className="min-w-0 flex-nowrap gap-2 whitespace-nowrap text-sm">
            <span className="flex min-w-0 max-w-64 shrink-0 gap-1 text-foreground-muted">
              <span className="shrink-0">In namespace</span>
              <Link to="/ipam" className="min-w-0 truncate font-medium text-foreground" title={pool.namespace}>
                {pool.namespace}
              </Link>
            </span>
            <Divider />
            <span className="min-w-0 truncate">
              <Joined inline>
                {getDefaultEntries(pool).map((entry) => (
                  <Phrase key={entry.label} entry={entry} />
                ))}
              </Joined>
            </span>
          </Row>
        </PoolHeader>
      }
    />
  );
}
