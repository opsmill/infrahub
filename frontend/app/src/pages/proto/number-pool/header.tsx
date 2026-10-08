// PROTO number-pool — page header: name, pool-type tag, description, ID, actions and what the pool allocates. Delete with the prototype.
import { Tooltip } from "@infrahub/ui";
import { FileCodeIcon, UserIcon } from "lucide-react";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { PoolActionsMenu } from "./actions-menu";
import type { Dataset } from "./data";

export const attrCode =
  "rounded-md bg-content-strong px-1.5 py-0.5 font-mono text-foreground text-xs";

const tag =
  "inline-flex h-6 shrink-0 items-center gap-1 rounded-md border border-border-strong px-2 font-medium text-foreground text-xs";

const schemaHref = "/schema?kind=InfraAutonomousSystem";

function PoolType({ dataset }: { dataset: Dataset }) {
  const { pool } = dataset;
  if (!pool.schemaDefined) {
    return (
      <Tooltip
        message="Created in Infrahub. Change its ranges from Actions → Edit."
        nonInteractiveTrigger
      >
        <span className={tag}>
          <UserIcon className="size-3.5 text-foreground-muted" aria-hidden />
          Managed by users
        </span>
      </Tooltip>
    );
  }
  return (
    <Tooltip
      message={`Created from the ${pool.targetKind}.${pool.targetAttribute} schema attribute. Change its ranges in the schema.`}
    >
      <Link to={schemaHref} className={classNames(tag, "no-underline hover:bg-highlight")}>
        <FileCodeIcon className="size-3.5 text-foreground-muted" aria-hidden />
        Managed by schema
      </Link>
    </Tooltip>
  );
}

function IdWithCopy({ id }: { id: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className="text-foreground-muted">ID</span>
      <Tooltip message={id}>
        <span className="font-mono text-xs" tabIndex={0}>
          {id.slice(0, 8)}
        </span>
      </Tooltip>
      <CopyToClipboardButton data={id} aria-label="Copy ID" />
    </span>
  );
}

function AllocationSentence({ dataset }: { dataset: Dataset }) {
  const { pool } = dataset;
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
      <span className="text-foreground-muted">Allocates to</span>
      <span className="font-medium">{pool.targetKind}</span>
      <span className="text-foreground-muted">attribute</span>
      <code className={attrCode}>{pool.targetAttribute}</code>
      {pool.scopedBy.length === 0 ? (
        <span className="text-foreground-muted">with no scope</span>
      ) : (
        <>
          <span className="text-foreground-muted">scoped by</span>
          <span className="font-medium">{pool.scopedBy.map((r) => r.label).join(" + ")}</span>
        </>
      )}
    </p>
  );
}

export function PoolHeader({ dataset }: { dataset: Dataset }) {
  const { pool } = dataset;
  return (
    <header className="flex flex-col gap-4 px-5 py-4">
      <div className="flex items-start gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="min-w-0 truncate font-bold text-xl" title={pool.name}>
              {pool.name}
            </h1>
            <PoolType dataset={dataset} />
          </div>
          {pool.description && (
            <p className="max-w-prose text-pretty text-foreground-muted text-sm">
              {pool.description}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <IdWithCopy id={pool.id} />
          <PoolActionsMenu dataset={dataset} />
        </div>
      </div>
      <AllocationSentence dataset={dataset} />
    </header>
  );
}
