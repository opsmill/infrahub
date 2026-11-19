// PROTOTYPE design-jam schema-migrations
import { Button, Card, CardContent, CardHeader, Meter, Spinner, Tooltip } from "@infrahub/ui";
import {
  type CSSProperties,
  createContext,
  Fragment,
  type ReactNode,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Col, Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";
import { Icon } from "@/shared/components/display/icon";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { DiffBadge, DiffRow } from "@/entities/diff/ui/node-diff/utils";

import {
  type Application,
  BRANCH,
  BRANCH_HISTORY,
  BRANCHED_FROM_VERSION,
  BranchPage,
  deletionTotals,
  FakeTabs,
  fmt,
  IdentifierFont,
  type Impact,
  type ImpactState,
  InlineMessage,
  MAIN,
  MAIN_HISTORY,
  MERGE_ATTEMPT,
  MIGRATION_LABEL,
  type Migration,
  MigrationTable,
  Mono,
  migrationsForOperation,
  NodeDiffStandIn,
  type Operation,
  PC_CHECK,
  PROPOSED_CHANGE,
  ProposedChangePage,
  pad,
  RUNNING_APPLICATION,
  revisionOf,
  SCHEMA_KIND_COUNT,
  type SchemaChange,
  STAGED_CHANGE,
  STAGED_MIGRATIONS,
  stagedImpact,
  sum,
  ToggleGroup,
  ViolationList,
  When,
} from "../context";

export const ONE_LIST_SCENES = [
  "Branch: Schema changes",
  "Main: Schema changes",
  "Branch: Details",
  "Schema viewer",
  "Proposed change: Schema changes",
  "Proposed change: merge rolled back",
] as const;
type SchemaTabScene = (typeof ONE_LIST_SCENES)[number];
export const DATA_STATES = ["loaded", "loading", "empty", "error", "no schema permission"] as const;
export type DataState = (typeof DATA_STATES)[number];

export const STAGED_STATES = ["staged", "applying", "applied"] as const;
export type StagedStatus = (typeof STAGED_STATES)[number];

type Props = {
  scene: SchemaTabScene;
  impactState: ImpactState;
  dataState: DataState;
  listWidth: number;
  stagedStatus: StagedStatus;
  toggleStyle: ToggleStyle;
  setScene: (scene: SchemaTabScene) => void;
};

/** The Diff tab shows "-" for a value that does not exist. */
const EMPTY = "-";

const NO_PERMISSION = "You need the Manage schema permission to change the staged schema.";
const STAGE_COMMAND = (branch: string) =>
  `infrahubctl schema load --stage${branch === MAIN ? "" : ` --branch ${branch}`} schemas/`;
const LOAD_COMMAND = (branch: string) =>
  `infrahubctl schema load${branch === MAIN ? "" : ` --branch ${branch}`} schemas/`;

/* ------------------------------------------------------------------ links between screens */

type Viewer = "list" | "graph" | "staged";

/** Where a link lands: a screen, and what is open or selected on it. */
type Target = { scene: SchemaTabScene; kind?: string; changeId?: string; viewer?: Viewer };

const Nav = createContext<{ go: (target: Target) => void; focus: Partial<Target> }>({
  go: () => undefined,
  focus: {},
});

/** The app's link look: a dotted underline that turns solid on hover. */
const LINK =
  "inline-flex items-center gap-1 rounded-sm text-left text-custom-blue-700 underline decoration-dotted underline-offset-2 hover:decoration-solid focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo dark:text-custom-blue-300";

function NavLink({
  to,
  children,
  className,
}: {
  to: Target;
  children: ReactNode;
  className?: string;
}) {
  const { go } = useContext(Nav);
  return (
    <button
      type="button"
      // Inside an accordion title, a link must not also open or close the accordion.
      onClick={(e) => {
        e.stopPropagation();
        go(to);
      }}
      className={classNames(LINK, className)}
    >
      {children}
      <Icon icon="mdi:arrow-right" aria-hidden="true" />
    </button>
  );
}

/** The selected schema change is kept in the page address, so a link can open it. */
function addressValue(key: string) {
  return new URLSearchParams(window.location.search).get(key) ?? undefined;
}

function setAddressValue(key: string, value: string) {
  const next = new URLSearchParams(window.location.search);
  next.set(key, value);
  window.history.replaceState(null, "", `?${next.toString()}`);
}

/** The staged change once applied: the newest schema change of the branch. */
const APPLIED_CHANGE: SchemaChange = {
  ...STAGED_CHANGE,
  id: "b31",
  version: 31,
  status: "applied",
  appliedAt: RUNNING_APPLICATION.at,
  applications: [
    {
      at: RUNNING_APPLICATION.at,
      status: "applied",
      migrations: STAGED_MIGRATIONS.map((m) => ({ ...m, status: "applied", completed: m.nodes })),
    },
  ],
};

/* ------------------------------------------------------------------ shared building blocks */

const STATUS: Record<string, { label: string; variant: BadgeProps["variant"]; icon: string }> = {
  staged: { label: "Staged", variant: "blue", icon: "mdi:tray-arrow-down" },
  applying: { label: "Applying", variant: "yellow", icon: "mdi:progress-clock" },
  running: { label: "Running", variant: "yellow", icon: "mdi:progress-clock" },
  applied: { label: "Applied", variant: "green", icon: "mdi:check" },
  failed: { label: "Failed", variant: "red", icon: "mdi:close-circle-outline" },
  "rolled back": { label: "Rolled back", variant: "warning", icon: "mdi:undo-variant" },
  skipped: { label: "Skipped", variant: "gray", icon: "mdi:debug-step-over" },
  waiting: { label: "Waiting", variant: "gray-outline", icon: "mdi:clock-outline" },
  "not run": { label: "Not run", variant: "gray-outline", icon: "mdi:minus-circle-outline" },
  passes: { label: "Passes", variant: "green", icon: "mdi:check" },
  "would fail": { label: "Would fail", variant: "red", icon: "mdi:close-circle-outline" },
  "not checked": {
    label: "Not checked",
    variant: "gray-outline",
    icon: "mdi:minus-circle-outline",
  },
};

/** One badge for every status: schema changes, runs, migrations and merge checks. */
function Status({ status }: { status: string }) {
  const s = STATUS[status] ?? {
    label: status,
    variant: "gray-outline",
    icon: "mdi:help-circle-outline",
  };
  return (
    <Badge variant={s.variant} className="shrink-0 gap-1">
      <Icon icon={s.icon} aria-hidden="true" />
      {s.label}
    </Badge>
  );
}

/**
 * A schema change gets its version when it is applied: a staged change shows the one it will get
 * in a dashed chip, and a failed load, which never gets one, shows a cross of the same width.
 */
function VersionChip({
  version,
  planned,
  failed,
}: {
  version: number | null;
  planned?: boolean;
  failed?: boolean;
}) {
  if (failed)
    return (
      <span className="relative shrink-0 rounded-md border border-transparent bg-danger-surface px-1.5 py-0.5 text-danger text-xs tabular-nums">
        <span className="invisible" aria-hidden="true">
          {pad(0)}
        </span>
        <span className="absolute inset-0 flex items-center justify-center">
          <Icon icon="mdi:close" aria-hidden="true" />
        </span>
        <span className="sr-only">No version</span>
      </span>
    );
  return (
    <span
      className={classNames(
        "shrink-0 rounded-md border px-1.5 py-0.5 text-xs tabular-nums",
        planned ? "border-dashed text-foreground-muted" : "border-transparent bg-content-strong"
      )}
    >
      {version === null ? EMPTY : pad(version)}
    </span>
  );
}

/** A schema change is always shown as its version, then its name. */
function ChangeName({ change }: { change: SchemaChange }) {
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-2">
      {change.version !== null ? (
        <VersionChip version={change.version} />
      ) : (
        change.status === "failed" && <VersionChip version={null} failed />
      )}
      <Mono className="font-semibold text-foreground text-sm">{change.name}</Mono>
    </span>
  );
}

const EMPTY_TONE = {
  neutral: "text-custom-blue-800 dark:text-custom-blue-300",
  success: "text-green-700 dark:text-green-300",
  danger: "text-danger",
};

/** Same look as the diff's "No changes detected": what happened, why, and what to do next. */
function EmptyState({
  icon,
  tone = "neutral",
  spin,
  title,
  children,
  actions,
}: {
  icon?: string;
  tone?: keyof typeof EMPTY_TONE;
  spin?: boolean;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex grow flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <div className="inline-flex rounded-full bg-content-strong p-3">
        {spin ? (
          <Spinner />
        ) : (
          <Icon
            icon={icon ?? "mdi:circle-off-outline"}
            className={classNames("text-2xl", EMPTY_TONE[tone])}
            aria-hidden="true"
          />
        )}
      </div>
      <h2 className="font-semibold text-lg">{title}</h2>
      {children && (
        <div className="flex max-w-prose flex-col items-center gap-1 text-foreground-muted text-sm">
          {children}
        </div>
      )}
      {actions && (
        <div className="flex max-w-full flex-wrap items-center justify-center gap-3">{actions}</div>
      )}
    </div>
  );
}

function CommandLine({ command }: { command: string }) {
  return (
    <span className="flex max-w-full items-center gap-1 rounded-md border bg-content-strong py-0.5 pr-0.5 pl-2 text-left">
      <code className="min-w-0 break-all font-mono text-foreground text-xs">{command}</code>
      <CopyToClipboardButton data={command} aria-label="Copy the command" />
    </span>
  );
}

function LoadState({ state, what }: { state: "loading" | "error"; what: string }) {
  if (state === "loading")
    return (
      <div className="flex grow items-center justify-center p-10">
        <LoadingIndicator message={`Loading the ${what}`} />
      </div>
    );
  return (
    <EmptyState
      icon="mdi:alert-circle-outline"
      tone="danger"
      title={`The ${what} could not be loaded`}
      actions={
        <Button size="sm" variant="outline">
          <Icon icon="mdi:refresh" aria-hidden="true" />
          Try again
        </Button>
      }
    >
      The server returned an error. The schema and the data did not change.
    </EmptyState>
  );
}

function SectionTitle({
  children,
  count,
  end,
}: {
  children: ReactNode;
  count?: number;
  end?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <h3 className="font-semibold text-sm">{children}</h3>
      {count !== undefined && <Badge>{fmt(count)}</Badge>}
      {end && <div className="ml-auto">{end}</div>}
    </div>
  );
}

/** The top of every record: what it is, its status, the facts, the actions, then any message. */
function RecordHeader({
  label,
  title,
  status,
  facts,
  actions,
  children,
}: {
  label: string;
  title: ReactNode;
  status?: ReactNode;
  facts?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section aria-label={label}>
      <Card className="gap-3 px-4 py-3">
        <Row className="flex-wrap items-start gap-x-4 gap-y-2">
          <Col className="min-w-0 grow gap-1">
            <Row className="flex-wrap items-center gap-2">
              {title}
              {status}
            </Row>
            {facts && (
              <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-foreground-muted text-sm">
                {facts}
              </div>
            )}
          </Col>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </Row>
        {children}
      </Card>
    </section>
  );
}

/** One list layout for every list beside a details panel: schema changes and kinds. */
function ListPanel({
  label,
  header,
  toolbar,
  children,
}: {
  label: string;
  header: ReactNode;
  toolbar?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-label={label} className="flex min-h-0 shrink-0 flex-col lg:w-(--list-width)">
      <Card className="min-h-0 overflow-hidden">
        <CardHeader>{header}</CardHeader>
        {toolbar && <div className="border-b px-3 py-2 text-sm">{toolbar}</div>}
        <nav aria-label={label} className="min-h-0 overflow-auto py-1">
          {children}
        </nav>
      </Card>
    </section>
  );
}

function ListGroup({
  title,
  count,
  danger,
  children,
}: {
  title?: string;
  count?: number;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <>
      {title && (
        <h3 className="flex items-center gap-2 px-3 pt-2 pb-1 font-semibold text-foreground-muted text-xs">
          {title}
          {count !== undefined && <Badge variant={danger ? "red" : undefined}>{count}</Badge>}
        </h3>
      )}
      <ul>{children}</ul>
    </>
  );
}

function ListItem({
  selected,
  onSelect,
  lead,
  title,
  meta,
  end,
}: {
  selected: boolean;
  onSelect: () => void;
  lead?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  end?: ReactNode;
}) {
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? "true" : undefined}
        onClick={onSelect}
        className={classNames(
          "flex w-full items-start gap-2 px-3 py-2 text-left text-sm",
          "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo focus-visible:ring-inset",
          selected ? "bg-selected" : "hover:bg-content-muted"
        )}
      >
        {lead}
        <span className="min-w-0 grow">
          <span className="block truncate">{title}</span>
          {meta && (
            <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-foreground-muted text-xs">
              {meta}
            </span>
          )}
        </span>
        {end}
      </button>
    </li>
  );
}

/* ------------------------------------------------------------------ collapsible sections */

export const SECTION_DEFAULTS = ["collapsed when long", "open", "collapsed"] as const;
export type SectionDefault = (typeof SECTION_DEFAULTS)[number];

/** Above this many kinds, "collapsed when long" starts the schema difference collapsed. */
const LONG_DIFFERENCE_KINDS = 5;

const SectionDefaultContext = createContext<SectionDefault>("collapsed when long");

/** The sections the viewer opened or closed stay so while they select other schema changes. */
const OpenSections = createContext<{
  toggled: Map<string, boolean>;
  set: (id: string, open: boolean) => void;
}>({ toggled: new Map(), set: () => {} });

function useSection(id: string, defaultOpen: boolean) {
  const { toggled, set } = useContext(OpenSections);
  return { open: toggled.get(id) ?? defaultOpen, setOpen: (open: boolean) => set(id, open) };
}

function kindCount(change: SchemaChange) {
  return new Set(change.operations.map((op) => op.kind)).size;
}

function useDifferenceOpen(change: SchemaChange) {
  const mode = useContext(SectionDefaultContext);
  const { focus } = useContext(Nav);
  if (focus.kind || mode === "open") return true;
  return mode === "collapsed when long" && kindCount(change) <= LONG_DIFFERENCE_KINDS;
}

/** Section titles stick under the details header while the card scrolls, or at the top when the page scrolls. */
function useStickyTitles(panel: { current: HTMLElement | null }) {
  useLayoutEffect(() => {
    const card = panel.current?.firstElementChild;
    const header = card?.firstElementChild;
    const content = header?.nextElementSibling;
    if (!(card instanceof HTMLElement && header instanceof HTMLElement)) return;
    const measure = () => {
      const overflow = getComputedStyle(card).overflowY;
      const cardScrolls =
        (overflow === "auto" || overflow === "scroll") && card.scrollHeight > card.clientHeight + 1;
      card.style.setProperty("--details-header", `${cardScrolls ? header.offsetHeight : 0}px`);
    };
    measure();
    const observer = new ResizeObserver(measure);
    for (const el of [card, header, content]) if (el) observer.observe(el);
    return () => observer.disconnect();
  }, [panel]);
}

function CollapsibleSection({
  id,
  title,
  count,
  danger,
  summary,
  defaultOpen = true,
  sectionRef,
  children,
}: {
  id: string;
  title: string;
  count?: number;
  danger?: boolean;
  summary?: ReactNode;
  defaultOpen?: boolean;
  sectionRef?: { current: HTMLElement | null };
  children: ReactNode;
}) {
  const { open, setOpen } = useSection(id, defaultOpen);
  const panelId = useId();
  return (
    <section ref={sectionRef} aria-label={title} className="flex flex-col gap-2">
      <div
        className="sticky z-20 -mx-4 flex flex-wrap items-center gap-x-3 gap-y-1 bg-card px-4 py-1.5"
        style={{ top: "var(--details-header, 0px)" }}
      >
        <h3>
          <button
            type="button"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen(!open)}
            className={classNames(
              "-mx-1 flex items-center gap-1.5 rounded-md px-1 py-0.5 text-left font-semibold text-sm",
              "hover:bg-content-muted focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo"
            )}
          >
            <Chevron open={open} className="text-foreground-muted" />
            {title}
            {count !== undefined && (
              <Badge variant={danger ? "red" : undefined}>{fmt(count)}</Badge>
            )}
          </button>
        </h3>
        {!open && summary && (
          <span className="flex items-center gap-2 text-foreground-muted text-sm">{summary}</span>
        )}
      </div>
      {open && (
        <div id={panelId} className="flex flex-col gap-2">
          {children}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ disclosure toggles */

export const TOGGLE_STYLES = ["two levels", "chevron rows", "labelled rows", "app today"] as const;
export type ToggleStyle = (typeof TOGGLE_STYLES)[number];

const ToggleStyleContext = createContext<ToggleStyle>("two levels");

function Chevron({
  open,
  icon = "mdi:chevron-right",
  className,
}: {
  open: boolean;
  icon?: string;
  className?: string;
}) {
  return (
    <Icon
      icon={icon}
      aria-hidden="true"
      className={classNames(
        "shrink-0 transition-transform duration-150 ease-out motion-reduce:transition-none",
        open && "rotate-90",
        className
      )}
    />
  );
}

/** A real button: keyboard and screen readers reach it, and its overlay makes the whole row clickable. */
function ToggleButton({
  open,
  onToggle,
  controls,
  label,
  level = 1,
}: {
  open: boolean;
  onToggle: () => void;
  controls: string;
  label: string;
  /** 1 opens a card or a list item; 2 opens a row inside an open card. */
  level?: 1 | 2;
}) {
  const style = useContext(ToggleStyleContext);
  const twoLevels = style === "two levels";
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className={classNames(
        "flex size-6 shrink-0 items-center justify-center rounded-md outline-hidden",
        twoLevels && level === 1
          ? "border bg-content text-foreground text-sm shadow-xs group-hover:border-border-strong"
          : twoLevels
            ? "text-foreground-muted text-sm group-hover:text-foreground"
            : "text-base text-foreground-muted group-hover:text-foreground",
        "after:absolute after:inset-0 after:z-10",
        "focus-visible:after:ring-2 focus-visible:after:ring-ring-halo focus-visible:after:ring-inset"
      )}
    >
      <Chevron open={open} icon={twoLevels && level === 2 ? "mdi:menu-right" : undefined} />
      <span className="sr-only">{label}</span>
    </button>
  );
}

function DisclosureHeader({
  open,
  onToggle,
  controls,
  label,
  children,
  end,
  endOnHover,
  className,
}: {
  open: boolean;
  onToggle: () => void;
  controls: string;
  label: string;
  children: ReactNode;
  end?: ReactNode;
  /** Shows `end` only while the header is hovered or holds keyboard focus. */
  endOnHover?: boolean;
  className?: string;
}) {
  return (
    <div
      className={classNames(
        "group relative flex flex-wrap items-center gap-2 py-2 pr-3 pl-2 hover:bg-content-muted",
        className
      )}
    >
      <ToggleButton open={open} onToggle={onToggle} controls={controls} label={label} />
      {children}
      {end && (
        <div
          className={classNames(
            "relative z-20 ml-auto",
            endOnHover &&
              "opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 motion-reduce:transition-none"
          )}
        >
          {end}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ schema difference */

// Only these properties change data on nodes; a label or description change has no migration.
const MIGRATING_PROPS = new Set(["name", "kind", "unique", "optional", "read_only"]);

const migrationsOf = (op: Operation, migrations: Migration[]) =>
  op.op === "el_prop" && !MIGRATING_PROPS.has(op.prop)
    ? []
    : migrationsForOperation(op, migrations);

const word = (section: "attributes" | "relationships") =>
  section === "attributes" ? "attribute" : "relationship";

type Described = {
  title: string;
  detail: string;
  before: ReactNode;
  after: ReactNode;
  status: "ADDED" | "REMOVED" | "UPDATED";
};

/** Each operation as one diff row: what changes, its value before, its value after. */
function describe(op: Operation): Described {
  switch (op.op) {
    case "node_add":
      return {
        title: "kind",
        detail: "kind added",
        before: EMPTY,
        after: "Added",
        status: "ADDED",
      };
    case "node_remove":
      return {
        title: "kind",
        detail: "kind removed, with every node",
        before: op.kind,
        after: EMPTY,
        status: "REMOVED",
      };
    case "node_prop":
      return {
        title: "kind",
        detail: `${op.prop} changed`,
        before: op.before,
        after: op.value,
        status: "UPDATED",
      };
    case "el_add":
      return {
        title: op.name,
        detail: `${word(op.section)} added`,
        before: EMPTY,
        after: op.detail,
        status: "ADDED",
      };
    case "el_remove":
      return {
        title: op.name,
        detail: `${word(op.section)} removed`,
        before: word(op.section) === "attribute" ? "Attribute" : "Relationship",
        after: EMPTY,
        status: "REMOVED",
      };
    case "el_prop":
      return op.prop === "name"
        ? {
            title: op.before,
            detail: `${word(op.section)} renamed`,
            before: op.before,
            after: op.value,
            status: "UPDATED",
          }
        : {
            title: op.name,
            detail: `${op.prop} changed`,
            before: op.before,
            after: op.value,
            status: "UPDATED",
          };
  }
}

type FailingAt = (path: string) => number;
const NONE_FAIL: FailingAt = () => 0;

const runOf = (m: Migration, progress?: Migration[]) =>
  progress?.find((r) => r.name === m.name && r.path === m.path) ?? m;

type Fact = [key: string, node: ReactNode];

/** Values on one line, each one separated from the next by a thin vertical rule. */
function Facts({ items, className }: { items: Fact[]; className?: string }) {
  return (
    <span className={classNames("flex flex-wrap items-center gap-x-2 gap-y-0.5", className)}>
      {items.map(([key, node], i) => (
        <Fragment key={key}>
          {i > 0 && <span aria-hidden="true" className="h-3.5 w-px shrink-0 bg-border-strong" />}
          {node}
        </Fragment>
      ))}
    </span>
  );
}

/** What a change does to data, as separate values: migrated nodes, deletions, nodes that would fail. */
function effectFacts({
  migrations,
  failingAt,
  progress,
  onShowFailing,
}: {
  migrations: Migration[];
  failingAt: FailingAt;
  progress?: Migration[];
  onShowFailing?: (path?: string) => void;
}): Fact[] {
  if (migrations.length === 0) return [["none", <span key="none">No change to data</span>]];
  const nodes = sum(migrations.map((m) => m.nodes));
  const kinds = new Set(migrations.map((m) => m.path.split(".")[0])).size;
  const deleted = deletionTotals(migrations);
  const failing = sum(migrations.map((m) => failingAt(m.path)));
  const runs = progress ? migrations.map((m) => runOf(m, progress)) : null;
  const done = runs ? sum(runs.map((r) => r.completed)) : 0;
  const count = (
    <span className="tabular-nums">
      {fmt(nodes)} nodes{kinds > 1 && ` on ${kinds} kinds`}
    </span>
  );
  let state: ReactNode = <span>Migrates {count}</span>;
  if (runs?.some((r) => r.status === "failed"))
    state = (
      <span className="flex items-center gap-1 text-danger">
        <Icon icon="mdi:close-circle-outline" aria-hidden="true" />
        Failed on {count}
      </span>
    );
  else if (runs?.some((r) => r.status === "running"))
    state = (
      <span className="flex items-center gap-2 tabular-nums">
        <Meter aria-label="Nodes done" value={done} maxValue={nodes} className="w-16" />
        {fmt(done)} of {fmt(nodes)} nodes migrated
      </span>
    );
  else if (runs?.every((r) => r.status === "applied"))
    state = (
      <span className="flex items-center gap-1 text-green-700 dark:text-green-300">
        <Icon icon="mdi:check" aria-hidden="true" />
        Migrated {count}
      </span>
    );
  else if (runs)
    state = (
      <span className="flex items-center gap-1">
        <Icon icon="mdi:clock-outline" aria-hidden="true" />
        Waiting to migrate {count}
      </span>
    );
  const facts: Fact[] = [["state", state]];
  for (const what of ["nodes", "values", "peers"] as const)
    if (deleted[what] > 0)
      facts.push([
        `deletes-${what}`,
        <span key={what} className="text-danger tabular-nums">
          deletes {fmt(deleted[what])} {what}
        </span>,
      ]);
  if (failing > 0) {
    const text = `${fmt(failing)} would fail`;
    facts.push([
      "failing",
      onShowFailing ? (
        <button
          key="failing"
          type="button"
          // Sits above the row's toggle overlay, and must not open or close the row.
          onClick={(e) => {
            e.stopPropagation();
            onShowFailing(migrations.find((m) => failingAt(m.path) > 0)?.path);
          }}
          className={classNames(LINK, "relative z-20 text-danger dark:text-danger")}
        >
          {text}
        </button>
      ) : (
        <span key="failing" className="text-danger tabular-nums">
          {text}
        </span>
      ),
    ]);
  }
  return facts;
}

function DataEffect(props: Parameters<typeof effectFacts>[0]) {
  return <Facts items={effectFacts(props)} className="text-foreground-muted text-xs" />;
}

/** The migrations of one change, at the row's text size, indented under the row it belongs to. */
function MigrationRows({
  id,
  migrations,
  failingAt,
  progress,
  caption,
  nested = true,
}: {
  id?: string;
  migrations: Migration[];
  failingAt: FailingAt;
  progress?: Migration[];
  caption: string;
  nested?: boolean;
}) {
  const anyFailing = migrations.some((m) => failingAt(m.path) > 0);
  const th = "py-1 pr-4 font-medium";
  const td = "py-1.5 pr-4";
  return (
    <div
      id={id}
      className={classNames("py-2 pr-3", nested ? "border-t bg-content-muted pl-8" : "pl-3")}
    >
      <div className={classNames(nested && "border-l-2 pl-3")}>
        <table className="w-full text-xs">
          <caption className="sr-only">{caption}</caption>
          <thead className="text-left text-subtle-muted">
            <tr>
              <th className={th}>Kind and field</th>
              <th className={th}>Migration</th>
              <th className={classNames(th, "text-right")}>Nodes</th>
              <th className={classNames(th, "text-right")}>Deletes</th>
              {anyFailing && <th className={classNames(th, "text-right")}>Would fail</th>}
              {progress && <th className={th}>Status</th>}
            </tr>
          </thead>
          <tbody>
            {migrations.map((m) => {
              const run = runOf(m, progress);
              const fail = failingAt(m.path);
              return (
                <tr key={`${m.name}:${m.path}`} className="border-t align-top">
                  <td className={td}>
                    <Mono className="text-foreground">{m.path}</Mono>
                    {run.error && <div className="mt-0.5 text-danger">{run.error}</div>}
                  </td>
                  <td className={td}>
                    <Tooltip message={<Mono>{m.name}</Mono>}>
                      <span>{MIGRATION_LABEL[m.name] ?? m.name}</span>
                    </Tooltip>
                  </td>
                  <td className={classNames(td, "text-right tabular-nums")}>
                    {progress && run.status === "running"
                      ? `${fmt(run.completed)} of ${fmt(run.nodes)}`
                      : fmt(m.nodes)}
                  </td>
                  <td className={classNames(td, "text-right tabular-nums")}>
                    {m.deletes ? (
                      <span className="text-danger">
                        {fmt(m.deletes.count)} {m.deletes.what}
                      </span>
                    ) : (
                      <span className="text-foreground-muted">{EMPTY}</span>
                    )}
                  </td>
                  {anyFailing && (
                    <td className={classNames(td, "text-right tabular-nums")}>
                      {fail > 0 ? (
                        <span className="text-danger">{fmt(fail)}</span>
                      ) : (
                        <span className="text-foreground-muted">{EMPTY}</span>
                      )}
                    </td>
                  )}
                  {progress && (
                    <td className="py-1">
                      <Status status={run.status} />
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OperationRow({
  op,
  migrations,
  failingAt,
  progress,
  onShowFailing,
}: {
  op: Operation;
  migrations: Migration[];
  failingAt: FailingAt;
  progress?: Migration[];
  onShowFailing?: (path?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const d = describe(op);
  const ms = migrationsOf(op, migrations);
  const hasMigrations = ms.length > 0;
  return (
    <>
      <div className={classNames("group relative flex", hasMigrations && "hover:bg-content-muted")}>
        <div className="flex w-8 shrink-0 pt-1.5 pl-2">
          {hasMigrations && (
            <ToggleButton
              open={open}
              onToggle={() => setOpen(!open)}
              controls={id}
              label={`Migrations for ${d.title}`}
              level={2}
            />
          )}
        </div>
        <div className="min-w-0 grow">
          <DiffRow
            className="pl-0"
            status={d.status}
            title={
              <div className="flex min-w-0 flex-col gap-1 py-2 pr-2">
                <span className="flex flex-wrap items-baseline gap-x-1.5">
                  <Mono className="font-semibold text-foreground">{d.title}</Mono>
                  <span className="text-foreground-muted">{d.detail}</span>
                </span>
                <DataEffect
                  migrations={ms}
                  failingAt={failingAt}
                  progress={progress}
                  onShowFailing={onShowFailing}
                />
              </div>
            }
            left={<span className="min-w-0 break-words">{d.before}</span>}
            right={<span className="min-w-0 break-words">{d.after}</span>}
          />
        </div>
      </div>
      {hasMigrations && open && (
        <MigrationRows
          id={id}
          migrations={ms}
          failingAt={failingAt}
          progress={progress}
          caption={`Migrations for ${d.title}`}
        />
      )}
    </>
  );
}

/** Column labels stay in the background: lighter and shorter than the rows they name. */
const DIFF_COLUMNS = (
  <div className="grid grid-cols-3 pl-8 text-subtle-muted text-xs">
    <span className="px-2 py-1">Change</span>
    <span className="px-2 py-1">Before</span>
    <span className="px-2 py-1">After</span>
  </div>
);

const DIFF_LABEL = { ADDED: "Added", REMOVED: "Removed", UPDATED: "Updated" } as const;

/** The same diff as the Diff tab, built from operations: one card per kind, one row per change. */
function SchemaDiff({
  change,
  migrations,
  failingAt = NONE_FAIL,
  progress,
  viewer,
  onShowFailing,
}: {
  change: SchemaChange;
  migrations: Migration[];
  failingAt?: FailingAt;
  progress?: Migration[];
  viewer: Viewer;
  onShowFailing?: (path?: string) => void;
}) {
  const { focus } = useContext(Nav);
  const baseId = useId();
  const focused = useRef<HTMLElement>(null);
  useEffect(() => focused.current?.scrollIntoView({ block: "start" }), []);
  const byKind = new Map<string, Operation[]>();
  for (const op of change.operations) byKind.set(op.kind, [...(byKind.get(op.kind) ?? []), op]);
  const kinds = [...byKind.keys()];
  const [openKinds, setOpenKinds] = useState<Set<string>>(() => new Set(kinds));
  const allOpen = openKinds.size === kinds.length;
  const toggleKind = (kind: string) =>
    setOpenKinds((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  const linked = new Set(change.operations.flatMap((op) => migrationsOf(op, migrations)));
  const extra = migrations.filter((m) => !linked.has(m));
  return (
    <Col className="gap-3">
      {kinds.length > 1 && (
        <Row className="items-center justify-between gap-2 px-1 text-sm">
          <span className="text-foreground-muted">{kinds.length} kinds</span>
          <button
            type="button"
            onClick={() => setOpenKinds(allOpen ? new Set() : new Set(kinds))}
            className={LINK}
          >
            {allOpen ? "Collapse all" : "Expand all"}
          </button>
        </Row>
      )}
      {[...byKind.entries()].map(([kind, ops], index) => {
        const status = ops.some((op) => op.op === "node_remove")
          ? "REMOVED"
          : ops.some((op) => op.op === "node_add")
            ? "ADDED"
            : "UPDATED";
        const kindMigrations = [...new Set(ops.flatMap((op) => migrationsOf(op, migrations)))];
        const changes = `${ops.length} change${ops.length === 1 ? "" : "s"}`;
        const isOpen = openKinds.has(kind);
        const panelId = `${baseId}-${index}`;
        return (
          <section
            key={kind}
            ref={kind === focus.kind ? focused : undefined}
            aria-label={kind}
            className="scroll-mt-4"
          >
            <Card className="overflow-hidden">
              <DisclosureHeader
                open={isOpen}
                onToggle={() => toggleKind(kind)}
                controls={panelId}
                label={`${kind}, ${DIFF_LABEL[status].toLowerCase()}, ${changes}`}
                endOnHover
                end={
                  <NavLink to={{ scene: "Schema viewer", viewer, kind }} className="text-xs">
                    View in the schema viewer
                  </NavLink>
                }
              >
                <span className="relative z-20 inline-flex">
                  <Tooltip message={DIFF_LABEL[status]} nonInteractiveTrigger>
                    <span className="inline-flex">
                      <DiffBadge status={status} size="icon" />
                    </span>
                  </Tooltip>
                </span>
                <Facts
                  className="text-foreground-muted text-xs"
                  items={[
                    [
                      "kind",
                      <span key="kind" className="font-semibold text-foreground text-sm">
                        {kind}
                      </span>,
                    ],
                    ["changes", <span key="changes">{changes}</span>],
                    ...effectFacts({
                      migrations: kindMigrations,
                      failingAt,
                      progress,
                      onShowFailing,
                    }),
                  ]}
                />
              </DisclosureHeader>
              {isOpen && (
                <div id={panelId} className="divide-y border-t bg-content">
                  {DIFF_COLUMNS}
                  {ops.map((op) => (
                    <OperationRow
                      key={JSON.stringify(op)}
                      op={op}
                      migrations={migrations}
                      failingAt={failingAt}
                      progress={progress}
                      onShowFailing={onShowFailing}
                    />
                  ))}
                </div>
              )}
            </Card>
          </section>
        );
      })}
      {extra.length > 0 && (
        <section aria-label="Other migrations">
          <Card className="overflow-hidden">
            <CardHeader>Other migrations Infrahub runs for this change</CardHeader>
            <MigrationRows
              migrations={extra}
              failingAt={failingAt}
              progress={progress}
              caption="Other migrations"
              nested={false}
            />
          </Card>
        </section>
      )}
    </Col>
  );
}

/* ------------------------------------------------------------------ staged */

function Big({ value, danger }: { value: number; danger?: boolean }) {
  return (
    <span className={classNames("font-semibold text-xl tabular-nums", danger && "text-danger")}>
      {fmt(value)}
    </span>
  );
}

function Tile({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Card className="min-w-0 gap-1 px-4 py-3">
      <span className="text-foreground-muted text-xs">{label}</span>
      {children}
    </Card>
  );
}

function Summary({ impact }: { impact: Impact }) {
  const kinds = new Set(impact.migrations.map((m) => m.path.split(".")[0]));
  const deleted = deletionTotals(impact.migrations);
  const hidden = sum(impact.denied.map((d) => d.count));
  const failing = impact.violations.length + hidden;
  return (
    <div className="grid @2xl:grid-cols-4 grid-cols-2 gap-3">
      <Tile label="Migrations">
        <Big value={impact.migrations.length} />
        <span className="text-foreground-muted text-xs">on {kinds.size} kinds</span>
      </Tile>
      <Tile label="Nodes changed">
        <Big value={sum(impact.migrations.map((m) => m.nodes))} />
      </Tile>
      <Tile label="Nodes that would fail">
        <Big value={failing} danger={failing > 0} />
        {hidden > 0 && (
          <span className="text-foreground-muted text-xs">
            {fmt(impact.violations.length)} listed, {fmt(hidden)} on a kind you cannot view
          </span>
        )}
      </Tile>
      <Tile label="Data deleted">
        <ul className="flex flex-col text-sm tabular-nums">
          <li>
            <span className="font-semibold text-danger">{fmt(deleted.nodes)}</span> nodes
          </li>
          <li>
            <span className="font-semibold text-danger">{fmt(deleted.values)}</span> attribute
            values
          </li>
          <li>
            <span className="font-semibold text-danger">{fmt(deleted.peers)}</span> relationship
            peers
          </li>
        </ul>
      </Tile>
    </div>
  );
}

function RecalculateButton({ canEdit }: { canEdit: boolean }) {
  const button = (
    <Button size="sm" variant="outline" isDisabled={!canEdit}>
      <Icon icon="mdi:refresh" aria-hidden="true" />
      Recalculate
    </Button>
  );
  return canEdit ? button : <Tooltip message={NO_PERMISSION}>{button}</Tooltip>;
}

/** Messages about the impact sit under the header; running and failed fill the body instead. */
function ImpactMessage({ impact, canEdit }: { impact: Impact; canEdit: boolean }) {
  if (impact.status !== "done") return null;
  if (impact.conflicts.length)
    return (
      <InlineMessage tone="danger" title="The staged schema no longer matches the branch schema">
        <ul className="list-disc pl-4">
          {impact.conflicts.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        Fix the schema file and stage it again, or discard this change.
      </InlineMessage>
    );
  if (impact.outOfDate)
    return (
      <InlineMessage
        tone="warning"
        title="The branch schema changed after the impact was calculated"
        action={<RecalculateButton canEdit={canEdit} />}
      >
        Calculated <When date={impact.calculatedAt} />. Recalculate before you apply.
      </InlineMessage>
    );
  return (
    <Row className="flex-wrap items-center gap-x-3 gap-y-1 text-foreground-muted text-sm">
      <span>
        Impact calculated <When date={impact.calculatedAt} />. Data changed on the branch since then
        is not counted.
      </span>
      <RecalculateButton canEdit={canEdit} />
    </Row>
  );
}

function StagedActions({
  blocked,
  canEdit,
  impact,
}: {
  blocked: boolean;
  canEdit: boolean;
  impact: Impact;
}) {
  const [confirm, setConfirm] = useState<"apply" | "discard" | null>(null);
  const deleted = deletionTotals(impact.migrations);
  const nodes = sum(impact.migrations.map((m) => m.nodes));
  const discard = (
    <Button variant="outline" size="sm" isDisabled={!canEdit} onPress={() => setConfirm("discard")}>
      Discard
    </Button>
  );
  const apply = (
    <Button size="sm" isDisabled={!canEdit || blocked} onPress={() => setConfirm("apply")}>
      Apply to branch
    </Button>
  );
  const applyWhy = !canEdit
    ? NO_PERMISSION
    : impact.status !== "done"
      ? "Available when the impact is calculated."
      : "Available when the staged schema matches the branch schema.";
  return (
    <Row className="gap-2">
      {canEdit ? discard : <Tooltip message={NO_PERMISSION}>{discard}</Tooltip>}
      {canEdit && !blocked ? apply : <Tooltip message={applyWhy}>{apply}</Tooltip>}
      <ModalConfirm
        isOpen={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm === "apply"
            ? "Apply the staged schema change?"
            : "Discard the staged schema change?"
        }
        description={
          confirm === "apply"
            ? `Infrahub recalculates the impact, then runs ${impact.migrations.length} migrations on ${fmt(nodes)} nodes. It deletes ${fmt(deleted.nodes)} nodes, ${fmt(deleted.values)} attribute values and ${fmt(deleted.peers)} relationship peers. If a node fails a check, nothing is applied and the change stays staged.`
            : "The staged schema change and its impact are deleted. The branch schema and data do not change."
        }
        confirmLabel={confirm === "apply" ? "Apply" : "Discard"}
        onConfirm={() => setConfirm(null)}
      />
    </Row>
  );
}

function ApplyProgress() {
  const migrations = RUNNING_APPLICATION.migrations;
  const ended = migrations.filter((m) => m.status === "applied" || m.status === "failed").length;
  return (
    <Col className="w-full gap-1 sm:w-72">
      <Meter
        label={`${ended} of ${migrations.length} migrations ended`}
        value={ended}
        maxValue={migrations.length}
      />
    </Col>
  );
}

type StagedEntry = { status: "staged" | "applying"; note: ReactNode; details: ReactNode };

/** What the list row of the staged change says about its impact. */
function stagedNote(status: "staged" | "applying", impactState: ImpactState): ReactNode {
  if (status === "applying") return null;
  const impact = stagedImpact(impactState);
  if (impact.status === "running") return <span>Calculating the impact</span>;
  if (impact.status === "failed") return <span className="text-danger">Impact not calculated</span>;
  if (impact.conflicts.length)
    return <span className="text-danger">No longer matches the branch</span>;
  const failing = impact.violations.length + sum(impact.denied.map((d) => d.count));
  return failing > 0 ? <span className="text-danger">{fmt(failing)} would fail</span> : null;
}

/** The staged change in the details panel: the same layout as an applied change, plus its actions. */
function StagedDetails({
  impactState,
  dataState,
  status,
  inProposedChange,
}: {
  impactState: ImpactState;
  dataState: DataState;
  status: "staged" | "applying";
  inProposedChange?: boolean;
}) {
  const [failFocus, setFailFocus] = useState<{ path?: string; n: number }>({ n: 0 });
  const failingSection = useRef<HTMLElement>(null);
  const panel = useRef<HTMLElement>(null);
  useStickyTitles(panel);
  const differenceOpen = useDifferenceOpen(STAGED_CHANGE);
  const failingOpen = useSection("failing", true);
  useEffect(() => {
    const section = failingSection.current;
    if (!failFocus.n || !section) return;
    const suffix = ` on ${failFocus.path}`;
    const group =
      [...section.querySelectorAll("section[aria-label]")].find((el) =>
        el.getAttribute("aria-label")?.endsWith(suffix)
      ) ?? section;
    group.scrollIntoView({ block: "center" });
    const flash = ["rounded-md", "ring-2", "ring-custom-blue-500"];
    group.classList.add(...flash);
    const timer = setTimeout(() => group.classList.remove(...flash), 1600);
    return () => clearTimeout(timer);
  }, [failFocus]);
  const applying = status === "applying";
  const calculated = stagedImpact(applying ? "done" : impactState);
  // An apply starts only after the check passes, so nothing would fail while it runs.
  const impact = applying ? { ...calculated, violations: [], denied: [] } : calculated;
  const canEdit = dataState !== "no schema permission";
  const blocked = impact.status !== "done" || impact.conflicts.length > 0;
  const failing = impact.violations.length + sum(impact.denied.map((d) => d.count));
  const failingAt: FailingAt = (path) =>
    impact.violations.filter((v) => v.path === path).length +
    sum(impact.denied.filter((d) => d.path === path).map((d) => d.count));
  return (
    <section
      ref={panel}
      aria-label="Staged schema change"
      className="flex min-h-0 min-w-0 grow flex-col"
    >
      <Card className="min-h-0 overflow-auto">
        <CardHeader className="sticky top-0 z-30 flex flex-wrap items-start gap-x-4 gap-y-2 px-4 py-3">
          <Col className="min-w-0 grow gap-1">
            <Row className="flex-wrap items-center gap-2">
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <VersionChip version={APPLIED_CHANGE.version} planned />
                <Mono className="font-semibold text-foreground text-sm">{STAGED_CHANGE.name}</Mono>
              </span>
              <Status status={status} />
            </Row>
            <span className="flex flex-wrap items-center gap-x-1.5 gap-y-1 font-normal text-foreground-muted text-sm">
              <span>
                {STAGED_CHANGE.operations.length} operations · staged{" "}
                <When date={STAGED_CHANGE.createdAt} /> on revision{" "}
                {pad(revisionOf(BRANCH_HISTORY)?.version ?? 0)} ·
              </span>
              <NavLink to={{ scene: "Schema viewer", viewer: "staged" }}>
                View the staged schema
              </NavLink>
            </span>
          </Col>
          <div className="flex shrink-0 flex-wrap items-center gap-2 font-normal">
            {applying ? (
              <ApplyProgress />
            ) : (
              <StagedActions blocked={blocked} canEdit={canEdit} impact={impact} />
            )}
          </div>
        </CardHeader>
        <CardContent className="@container flex flex-col gap-5 p-4">
          {inProposedChange && (
            <InlineMessage tone="info" title="Not part of this merge">
              A staged change stays on the branch until it is applied. Apply it to add it to this
              proposed change.
            </InlineMessage>
          )}
          {applying ? (
            <Row className="flex-wrap items-center gap-x-3 gap-y-1 text-foreground-muted text-sm">
              <span>
                Applying since <When date={RUNNING_APPLICATION.at} />. The branch moves to revision{" "}
                {pad(APPLIED_CHANGE.version ?? 0)} when every migration ends.
              </span>
              <a href="/tasks" className={LINK}>
                View the task
                <Icon icon="mdi:open-in-new" aria-hidden="true" />
              </a>
            </Row>
          ) : (
            <ImpactMessage impact={impact} canEdit={canEdit} />
          )}
          {impact.status === "running" ? (
            <EmptyState spin title="Calculating the impact">
              Started 1 minute ago. The counts, the schema difference and the nodes that would fail
              appear when it ends. You can discard the change meanwhile.
            </EmptyState>
          ) : impact.status === "failed" ? (
            <EmptyState
              icon="mdi:alert-circle-outline"
              tone="danger"
              title="The impact could not be calculated"
              actions={<RecalculateButton canEdit={canEdit} />}
            >
              {impact.error}
            </EmptyState>
          ) : (
            <>
              <CollapsibleSection
                id="impact"
                title="Impact on data"
                summary={`${fmt(impact.migrations.length)} migrations · ${fmt(sum(impact.migrations.map((m) => m.nodes)))} nodes changed`}
              >
                <Summary impact={impact} />
              </CollapsibleSection>
              <CollapsibleSection
                id="difference"
                title="Schema difference"
                count={STAGED_CHANGE.operations.length}
                summary={`${kindCount(STAGED_CHANGE)} kinds`}
                defaultOpen={differenceOpen}
              >
                <SchemaDiff
                  change={STAGED_CHANGE}
                  migrations={impact.migrations}
                  failingAt={failingAt}
                  progress={applying ? RUNNING_APPLICATION.migrations : undefined}
                  viewer="staged"
                  onShowFailing={(path) => {
                    failingOpen.setOpen(true);
                    setFailFocus((prev) => ({ path, n: prev.n + 1 }));
                  }}
                />
              </CollapsibleSection>
              <CollapsibleSection
                id="failing"
                title="Would fail"
                count={failing}
                danger={failing > 0}
                sectionRef={failingSection}
              >
                {failing === 0 ? (
                  <p className="flex items-center gap-1.5 text-foreground-muted text-sm">
                    <Icon
                      icon="mdi:check-circle-outline"
                      className="shrink-0 text-green-700 dark:text-green-300"
                      aria-hidden="true"
                    />
                    {applying ? (
                      "No node would fail. Infrahub checked every node when the apply started."
                    ) : (
                      <span>
                        No node would fail. Infrahub checked every node the migrations change,{" "}
                        <When date={impact.calculatedAt} />.
                      </span>
                    )}
                  </p>
                ) : (
                  <Card className="py-3">
                    <ViolationList violations={impact.violations} denied={impact.denied} />
                  </Card>
                )}
              </CollapsibleSection>
            </>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

/* ------------------------------------------------------------------ merge into main */

type MergeMode = "review" | "rolled back";

const REPLAY = PROPOSED_CHANGE.replay;
const FAIL_INDEX = REPLAY.findIndex((c) => c.id === PC_CHECK.failingChangeId);
const FAILING_VERSION = pad(REPLAY[FAIL_INDEX]?.version ?? 0);

function mergeStepOf(change: SchemaChange, mode: MergeMode) {
  const index = REPLAY.findIndex((c) => c.id === change.id);
  if (index < 0) return null;
  const result: string =
    mode === "rolled back"
      ? (MERGE_ATTEMPT.applications[index]?.status ?? "not run")
      : index < FAIL_INDEX
        ? "passes"
        : index === FAIL_INDEX
          ? "would fail"
          : "not checked";
  return { onMain: PROPOSED_CHANGE.mainVersion + index + 1, result };
}

function MergeStepNote({ result }: { result: string }) {
  const muted = "text-foreground-muted text-sm";
  switch (result) {
    case "passes":
      return (
        <p className={muted}>
          Passes against the current main, checked <When date={PC_CHECK.checkedAt} />.
        </p>
      );
    case "would fail":
      return (
        <>
          <p className="text-sm">
            {PC_CHECK.message} Checked <When date={PC_CHECK.checkedAt} />.
          </p>
          <Card className="py-3">
            <ViolationList violations={PC_CHECK.violations} />
          </Card>
        </>
      );
    case "not checked":
      return <p className={muted}>Not checked, because {FAILING_VERSION} before it would fail.</p>;
    case "rolled back":
      return (
        <p className={muted}>
          Applied on main during the merge <When date={MERGE_ATTEMPT.at} />, then rolled back when{" "}
          {FAILING_VERSION} failed.
        </p>
      );
    case "failed":
      return (
        <p className="text-sm">
          Failed during the merge <When date={MERGE_ATTEMPT.at} />: {MERGE_ATTEMPT.error}
        </p>
      );
    default:
      return <p className={muted}>Did not run, because {FAILING_VERSION} failed before it.</p>;
  }
}

function MergeStepDetails({ change, mode }: { change: SchemaChange; mode: MergeMode }) {
  const step = mergeStepOf(change, mode);
  return (
    <section aria-label="Merge into main" className="flex flex-col gap-2">
      <SectionTitle>Merge into main</SectionTitle>
      {step ? (
        <>
          <Row className="flex-wrap items-center gap-2 text-sm">
            Becomes
            <VersionChip version={step.onMain} />
            on main
            <Status status={step.result} />
          </Row>
          <MergeStepNote result={step.result} />
        </>
      ) : (
        <p className="text-foreground-muted text-sm">
          This load failed on the branch, so it has no version and the merge does not include it.
        </p>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ schema changes: list and details */

function RunRow({ app, index }: { app: Application; index: number }) {
  const style = useContext(ToggleStyleContext);
  const [open, setOpen] = useState(app.status === "failed");
  const id = useId();
  const deleted = deletionTotals(app.migrations);
  const total = deleted.nodes + deleted.values + deleted.peers;
  const summary = (
    <>
      <span className="font-medium">Run {index + 1}</span>
      <When date={app.at} />
      <Status status={app.status} />
      <span className="text-foreground-muted">
        {app.migrations.length} migration{app.migrations.length === 1 ? "" : "s"}
      </span>
      {total > 0 && <span className="text-danger text-xs">deleted {fmt(total)}</span>}
    </>
  );
  const body = (
    <>
      {app.error && <p className="px-3 py-1.5 text-danger text-sm">{app.error}</p>}
      <MigrationTable
        migrations={app.migrations}
        mode="run"
        caption={`Migrations of run ${index + 1}`}
      />
    </>
  );
  if (style === "app today")
    return (
      <li className="overflow-hidden rounded-lg border">
        <Accordion
          defaultOpen={app.status === "failed"}
          title={
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5 pr-3 font-normal text-sm">
              {summary}
            </span>
          }
        >
          <div className="border-t">{body}</div>
        </Accordion>
      </li>
    );
  return (
    <li className="overflow-hidden rounded-lg border">
      <DisclosureHeader
        open={open}
        onToggle={() => setOpen(!open)}
        controls={id}
        label={`Run ${index + 1}`}
        className="gap-x-3 py-1 text-sm"
      >
        {summary}
      </DisclosureHeader>
      {open && (
        <div id={id} className="border-t">
          {body}
        </div>
      )}
    </li>
  );
}

function ChangeDetails({ change, merge }: { change: SchemaChange; merge?: MergeMode }) {
  const lastRun = change.applications.at(-1);
  const migrations = lastRun?.migrations ?? [];
  const failingAt: FailingAt | undefined =
    merge === "review" && change.id === PC_CHECK.failingChangeId
      ? (path) => PC_CHECK.violations.filter((v) => v.path === path).length
      : undefined;
  const panel = useRef<HTMLElement>(null);
  useStickyTitles(panel);
  const differenceOpen = useDifferenceOpen(change);
  return (
    <section ref={panel} aria-label={change.name} className="flex min-h-0 min-w-0 grow flex-col">
      <Card className="min-h-0 overflow-auto">
        <CardHeader className="sticky top-0 z-30 flex flex-col gap-1 px-4 py-3">
          <Row className="flex-wrap items-center gap-2">
            <ChangeName change={change} />
            {change.status !== "applied" && <Status status={change.status} />}
            {change.fromUpgrade && <Badge variant="purple">Before the upgrade</Badge>}
          </Row>
          <span className="font-normal text-foreground-muted text-sm">
            {change.status === "failed" ? "Loaded" : "Applied"}{" "}
            <When date={change.appliedAt ?? change.createdAt} />
            {change.parent && (
              <>
                {" "}
                · after <Mono>{change.parent}</Mono>
              </>
            )}
          </span>
        </CardHeader>
        <CardContent className="flex flex-col gap-5 p-4">
          {change.fromUpgrade && (
            <InlineMessage tone="info" title="Loads made before the upgrade are combined here">
              Their order is not known.
            </InlineMessage>
          )}
          {merge && <MergeStepDetails change={change} mode={merge} />}
          <CollapsibleSection
            id="difference"
            title="Schema difference"
            count={change.operations.length}
            summary={`${kindCount(change)} kinds`}
            defaultOpen={differenceOpen}
          >
            <SchemaDiff
              change={change}
              migrations={migrations}
              failingAt={failingAt}
              progress={change.status === "failed" ? migrations : undefined}
              viewer="list"
            />
          </CollapsibleSection>
          <CollapsibleSection
            id="runs"
            title="Runs on this branch"
            count={change.applications.length}
            danger={lastRun?.status === "failed"}
            summary={
              lastRun && (
                <>
                  Last run <When date={lastRun.at} />
                  <Status status={lastRun.status} />
                </>
              )
            }
          >
            <ul className="flex flex-col gap-1">
              {change.applications.map((app, i) => (
                <RunRow key={app.at} app={app} index={i} />
              ))}
            </ul>
          </CollapsibleSection>
        </CardContent>
      </Card>
    </section>
  );
}

function SchemaChangesView({
  branch,
  history,
  initialIds,
  addressKey,
  dataState,
  listWidth,
  header,
  merge,
  staged,
}: {
  branch: string;
  history: SchemaChange[];
  /** The first one that is in the list is selected; otherwise the staged change, then the newest. */
  initialIds: (string | undefined)[];
  addressKey: string;
  dataState: DataState;
  listWidth: number;
  header: ReactNode;
  merge?: MergeMode;
  staged?: StagedEntry;
}) {
  const inList = (id?: string): id is string =>
    !!id && (history.some((c) => c.id === id) || (!!staged && id === STAGED_CHANGE.id));
  const failed = history.filter((c) => c.status === "failed");
  const applied = history
    .filter((c) => c.status !== "failed")
    .sort((a, b) => (b.version ?? 0) - (a.version ?? 0));
  const fallback = staged ? STAGED_CHANGE.id : (applied[0]?.id ?? "");
  const [selectedId, setSelectedId] = useState(() => initialIds.find(inList) ?? fallback);
  const [toggled, setToggled] = useState<Map<string, boolean>>(() => new Map());
  const openSections = {
    toggled,
    set: (id: string, open: boolean) => setToggled((prev) => new Map(prev).set(id, open)),
  };
  const current = inList(selectedId) ? selectedId : fallback;
  const listed = dataState === "loaded" || dataState === "no schema permission";
  useEffect(() => {
    if (listed && current) setAddressValue(addressKey, current);
  }, [listed, addressKey, current]);
  if (dataState === "loading" || dataState === "error")
    return (
      <LoadState
        state={dataState}
        what={merge ? "schema changes of this proposed change" : "schema changes"}
      />
    );
  if (dataState === "empty" && merge)
    return (
      <EmptyState icon="mdi:source-merge" title="No schema change in this proposed change">
        Merging it changes data only. Main stays at schema revision{" "}
        {pad(PROPOSED_CHANGE.mainVersion)}.
      </EmptyState>
    );
  if (dataState === "empty")
    return (
      <EmptyState
        icon="mdi:history"
        title={`No schema change on ${branch === MAIN ? "main" : "this branch"}`}
        actions={
          <Col className="max-w-full items-center gap-2">
            <CommandLine command={STAGE_COMMAND(branch)} />
            <CommandLine command={LOAD_COMMAND(branch)} />
            <NavLink to={{ scene: "Schema viewer", viewer: "list" }}>View the schema</NavLink>
          </Col>
        }
      >
        {branch !== MAIN && (
          <p>This branch uses the schema of main at revision {pad(BRANCHED_FROM_VERSION)}.</p>
        )}
        <p>
          Stage a schema file to view its effect on data before you apply it, or load it to apply it
          now. Both add a schema change to this list.
        </p>
      </EmptyState>
    );
  const selected = history.find((c) => c.id === current);

  const item = (c: SchemaChange) => {
    const step = merge ? mergeStepOf(c, merge) : null;
    return (
      <ListItem
        key={c.id}
        selected={c.id === current}
        onSelect={() => setSelectedId(c.id)}
        lead={<VersionChip version={c.version} failed={c.version === null} />}
        title={<Mono className="text-foreground">{c.name}</Mono>}
        meta={
          <>
            <span>
              <When date={c.appliedAt ?? c.createdAt} />
              {c.applications.length > 1 && ` · ran ${c.applications.length} times`}
              {c.version === null && " · no version"}
            </span>
            {step && (
              <>
                <span className="flex items-center gap-1">
                  <Icon icon="mdi:arrow-right" aria-hidden="true" />
                  <span className="tabular-nums">{pad(step.onMain)}</span> on main
                </span>
                <Status status={step.result} />
              </>
            )}
          </>
        }
      />
    );
  };

  return (
    <OpenSections.Provider value={openSections}>
      <div
        className="flex min-h-0 grow flex-col gap-3 lg:flex-row"
        style={{ "--list-width": `${listWidth}px` } as CSSProperties}
      >
        <ListPanel label="Schema changes" header={header}>
          {(staged || !merge) && (
            <ListGroup
              title={merge ? "Staged, not merged" : "Staged"}
              count={staged ? 1 : undefined}
            >
              {staged ? (
                <ListItem
                  key={STAGED_CHANGE.id}
                  selected={current === STAGED_CHANGE.id}
                  onSelect={() => setSelectedId(STAGED_CHANGE.id)}
                  lead={<VersionChip version={APPLIED_CHANGE.version} planned />}
                  title={<Mono className="text-foreground">{STAGED_CHANGE.name}</Mono>}
                  meta={
                    <>
                      <Status status={staged.status} />
                      <span>
                        Becomes {pad(APPLIED_CHANGE.version ?? 0)}
                        {merge && " on the branch"} when applied
                      </span>
                      {staged.note}
                    </>
                  }
                />
              ) : (
                <li className="px-3 pb-2 text-foreground-muted text-xs">
                  Nothing staged. A staged schema file appears here with its impact.
                </li>
              )}
            </ListGroup>
          )}
          {failed.length > 0 && (
            <ListGroup
              title={merge ? "Failed loads, not merged" : "Failed loads"}
              count={failed.length}
              danger
            >
              {failed.map(item)}
            </ListGroup>
          )}
          <ListGroup title="Applied" count={applied.length}>
            {applied.map(item)}
          </ListGroup>
        </ListPanel>
        {current === STAGED_CHANGE.id && staged ? (
          <Fragment key={STAGED_CHANGE.id}>{staged.details}</Fragment>
        ) : (
          selected && <ChangeDetails key={selected.id} change={selected} merge={merge} />
        )}
      </div>
    </OpenSections.Provider>
  );
}

/* ------------------------------------------------------------------ branch Schema tab */

function BranchSchemaTab({
  onMain,
  stagedStatus,
  impactState,
  dataState,
  listWidth,
}: {
  onMain: boolean;
  stagedStatus: StagedStatus;
  impactState: ImpactState;
  dataState: DataState;
  listWidth: number;
}) {
  const { focus } = useContext(Nav);
  const [section, setSection] = useState("changes");
  const branch = onMain ? MAIN : BRANCH;
  const history = onMain
    ? MAIN_HISTORY
    : stagedStatus === "applied"
      ? [...BRANCH_HISTORY, APPLIED_CHANGE]
      : BRANCH_HISTORY;
  const stagedNow =
    !onMain && dataState !== "empty" && stagedStatus !== "applied" ? stagedStatus : null;
  const loaded = dataState !== "loading" && dataState !== "error" && dataState !== "empty";
  const applied = history.filter((c) => c.status === "applied").length;
  const revision = revisionOf(history);
  const list = (
    <SchemaChangesView
      key={`${branch}-${dataState}-${stagedStatus}-${impactState}`}
      branch={branch}
      history={history}
      initialIds={[focus.changeId, addressValue("change"), onMain ? "m-failed-1" : undefined]}
      addressKey="change"
      dataState={dataState}
      listWidth={listWidth}
      staged={
        stagedNow
          ? {
              status: stagedNow,
              note: stagedNote(stagedNow, impactState),
              details: (
                <StagedDetails impactState={impactState} dataState={dataState} status={stagedNow} />
              ),
            }
          : undefined
      }
      header={
        <span className="flex flex-col">
          <span>
            Revision <span className="tabular-nums">{pad(revision?.version ?? 0)}</span>
          </span>
          <span className="font-normal text-foreground-muted text-xs">
            {onMain ? "Main" : `Branched from main at ${pad(BRANCHED_FROM_VERSION)}`}
          </span>
        </span>
      }
    />
  );
  return (
    <BranchPage
      branch={branch}
      isDefault={onMain}
      baseTabs={
        onMain
          ? [
              { id: "details", label: "Details" },
              { id: "schema", label: "Schema" },
            ]
          : undefined
      }
      active="schema"
    >
      {onMain ? (
        <div className="flex min-h-0 grow flex-col gap-3 p-3">{list}</div>
      ) : (
        <>
          <FakeTabs
            label="Schema sections"
            active={section}
            onSelect={setSection}
            tabs={[
              {
                id: "changes",
                label: "Schema changes",
                count: loaded ? applied : undefined,
                live: true,
              },
              { id: "diff", label: "Diff", live: true },
            ]}
          />
          <div className="flex min-h-0 grow flex-col gap-3 border-t p-3">
            {section === "changes" ? (
              list
            ) : (
              <Card>
                <NodeDiffStandIn />
              </Card>
            )}
          </div>
        </>
      )}
    </BranchPage>
  );
}

/* ------------------------------------------------------------------ branch Details tab */

function DetailLabel({ icon, children }: { icon: string; children: ReactNode }) {
  return (
    <dt className="flex items-center gap-1.5 text-foreground-muted">
      <Icon icon={icon} aria-hidden="true" />
      {children}
    </dt>
  );
}

function BranchDetailsView({
  dataState,
  stagedStatus,
}: {
  dataState: DataState;
  stagedStatus: StagedStatus;
}) {
  const history = stagedStatus === "applied" ? [...BRANCH_HISTORY, APPLIED_CHANGE] : BRANCH_HISTORY;
  const last = revisionOf(history);
  const empty = dataState === "empty";
  return (
    <BranchPage branch={BRANCH} active="details">
      <div className="p-3">
        {dataState === "loading" || dataState === "error" ? (
          <LoadState state={dataState} what="branch" />
        ) : (
          <Card>
            <CardHeader>Details</CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-4">
                <DetailLabel icon="mdi:card-account-details-outline">Name</DetailLabel>
                <dd className="min-w-0 break-all sm:col-span-3">{BRANCH}</dd>
                <DetailLabel icon="mdi:sync">Sync with Git</DetailLabel>
                <dd className="sm:col-span-3">No</dd>
                <DetailLabel icon="mdi:source-branch">Last rebase</DetailLabel>
                <dd className="sm:col-span-3">5 days ago</dd>
                <DetailLabel icon="mdi:file-tree-outline">Schema revision</DetailLabel>
                <dd className="min-w-0 sm:col-span-3">
                  {empty ? (
                    `${pad(BRANCHED_FROM_VERSION)}, the same as main: no schema change on this branch`
                  ) : (
                    <Row className="flex-wrap items-center gap-x-3 gap-y-1">
                      {last && <ChangeName change={last} />}
                      <NavLink to={{ scene: "Branch: Schema changes", changeId: last?.id }}>
                        View in Schema changes
                      </NavLink>
                    </Row>
                  )}
                </dd>
                <DetailLabel icon="mdi:tray-arrow-down">Staged schema change</DetailLabel>
                <dd className="min-w-0 sm:col-span-3">
                  {empty || stagedStatus === "applied" ? (
                    "None"
                  ) : (
                    <Row className="flex-wrap items-center gap-x-3 gap-y-1">
                      <ChangeName change={STAGED_CHANGE} />
                      <Status status={stagedStatus === "applying" ? "applying" : "staged"} />
                      <NavLink to={{ scene: "Branch: Schema changes", changeId: STAGED_CHANGE.id }}>
                        View in Schema changes
                      </NavLink>
                    </Row>
                  )}
                </dd>
              </dl>
            </CardContent>
          </Card>
        )}
      </div>
    </BranchPage>
  );
}

/* ------------------------------------------------------------------ schema viewer */

type KindRow = { kind: string; ops: number; removed: boolean };

const STAGED_OPS_BY_KIND = (() => {
  const counts = new Map<string, KindRow>();
  for (const op of STAGED_CHANGE.operations) {
    const row = counts.get(op.kind) ?? { kind: op.kind, ops: 0, removed: false };
    row.ops += 1;
    if (op.op === "node_remove") row.removed = true;
    counts.set(op.kind, row);
  }
  return counts;
})();

/** The kinds the stand-in lists: every kind the mock data names, plus a few unchanged ones. */
const KIND_ROWS: KindRow[] = [
  ...new Set([
    ...STAGED_OPS_BY_KIND.keys(),
    ...[...BRANCH_HISTORY, ...MAIN_HISTORY].flatMap((c) => c.operations.map((op) => op.kind)),
    "InfraAutonomousSystem",
    "InfraBFDProfile",
    "IpamNamespace",
    "LocationBuilding",
    "OrganizationProvider",
  ]),
]
  .map((kind) => STAGED_OPS_BY_KIND.get(kind) ?? { kind, ops: 0, removed: false })
  .sort((a, b) => a.kind.localeCompare(b.kind));

type AttrRow = {
  name: string;
  kind: string;
  optional: [string, string];
  label: [string, string];
};

const LOCATION_SITE_ATTRIBUTES: AttrRow[] = [
  { name: "name", kind: "Text", optional: ["no", "no"], label: ["Name", "Name"] },
  { name: "shortname", kind: "Text", optional: ["yes", "no"], label: ["Short name", "Short name"] },
  {
    name: "description",
    kind: "TextArea",
    optional: ["yes", "yes"],
    label: ["Description", "Notes"],
  },
  { name: "region", kind: "Dropdown", optional: ["yes", "yes"], label: ["Region", "Region"] },
  {
    name: "facility_code",
    kind: "Text",
    optional: ["yes", "yes"],
    label: ["Facility code", "Facility code"],
  },
  { name: "timezone", kind: "Text", optional: ["yes", "yes"], label: ["Timezone", "Timezone"] },
];

function SchemaViewerView({
  stagedStatus,
  dataState,
}: {
  stagedStatus: StagedStatus;
  dataState: DataState;
}) {
  const { focus } = useContext(Nav);
  const hasStaged = stagedStatus !== "applied" && dataState !== "empty";
  const [view, setView] = useState<Viewer>(focus.viewer ?? (hasStaged ? "staged" : "list"));
  const [changedOnly, setChangedOnly] = useState(true);
  const [selected, setSelected] = useState(focus.kind ?? "LocationSite");
  const staged = view === "staged";
  const revision = revisionOf(
    stagedStatus === "applied" ? [...BRANCH_HISTORY, APPLIED_CHANGE] : BRANCH_HISTORY
  );
  const rows = KIND_ROWS.filter((r) => !staged || !changedOnly || r.ops > 0);
  const selectedRow = STAGED_OPS_BY_KIND.get(selected);
  const cell = (pair: [string, string]) => {
    const [before, after] = pair;
    if (!staged || before === after) return <span>{staged ? after : before}</span>;
    return (
      <span className="flex flex-wrap items-center gap-1.5">
        <span className="text-foreground-muted line-through">{before}</span>
        <span className="rounded-sm bg-blue-100 px-1 font-medium text-blue-900 dark:bg-blue-400/15 dark:text-blue-300">
          {after}
        </span>
      </span>
    );
  };

  const kindList = (
    <ListPanel
      label="Kinds"
      header={
        <span className="flex items-center gap-2">
          Kinds <Badge>{staged && changedOnly ? rows.length : SCHEMA_KIND_COUNT}</Badge>
        </span>
      }
      toolbar={
        staged ? (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={changedOnly}
              onChange={(e) => setChangedOnly(e.target.checked)}
            />
            Changed kinds only
          </label>
        ) : undefined
      }
    >
      <ListGroup>
        {rows.map((r) => (
          <ListItem
            key={r.kind}
            selected={r.kind === selected}
            onSelect={() => setSelected(r.kind)}
            title={
              <span className={classNames(staged && r.removed && "line-through")}>{r.kind}</span>
            }
            end={
              staged && r.ops > 0 ? (
                <DiffBadge status={r.removed ? "REMOVED" : "UPDATED"} className="shrink-0">
                  {r.removed ? "Removed" : r.ops}
                </DiffBadge>
              ) : undefined
            }
          />
        ))}
      </ListGroup>
    </ListPanel>
  );

  const kindDetails = (
    <section aria-label={selected} className="flex min-h-0 min-w-0 grow flex-col">
      <Card className="min-h-0 overflow-auto">
        <CardHeader className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
          <span className="font-semibold text-base">{selected}</span>
          {selected === "LocationSite" && (
            <span className="font-normal text-foreground-muted text-sm">
              Location · 1,302 nodes on this branch
            </span>
          )}
          {staged && selectedRow && (
            <NavLink
              to={{ scene: "Branch: Schema changes", changeId: STAGED_CHANGE.id, kind: selected }}
              className="ml-auto text-sm"
            >
              View the impact on data
            </NavLink>
          )}
        </CardHeader>
        {!staged && hasStaged && selectedRow && (
          <div className="border-b px-4 py-2">
            <InlineMessage
              tone="info"
              title={`The staged schema change has ${selectedRow.ops} operation${selectedRow.ops === 1 ? "" : "s"} on ${selected}`}
              action={
                <button
                  type="button"
                  onClick={() => setView("staged")}
                  className={classNames(LINK, "text-sm")}
                >
                  View in Staged
                </button>
              }
            >
              This list shows the schema in use on the branch.
            </InlineMessage>
          </div>
        )}
        {selected === "LocationSite" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Attributes of LocationSite</caption>
              <thead className="text-left text-foreground-muted text-xs">
                <tr className="border-b">
                  <th className="px-4 py-2 font-medium">Attribute</th>
                  <th className="px-4 py-2 font-medium">Kind</th>
                  <th className="px-4 py-2 font-medium">Optional</th>
                  <th className="px-4 py-2 font-medium">Label</th>
                </tr>
              </thead>
              <tbody>
                {LOCATION_SITE_ATTRIBUTES.map((a) => (
                  <tr key={a.name} className="border-b last:border-b-0">
                    <td className="px-4 py-2">
                      <Mono className="text-foreground text-sm">{a.name}</Mono>
                    </td>
                    <td className="px-4 py-2">{a.kind}</td>
                    <td className="px-4 py-2">{cell(a.optional)}</td>
                    <td className="px-4 py-2">{cell(a.label)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-4 py-6 text-foreground-muted text-sm">
            Stand-in: the existing kind details of the schema viewer
            {staged && (
              <>
                , read with <Mono>staged=true</Mono>
              </>
            )}
            .
          </p>
        )}
      </Card>
    </section>
  );

  let body: ReactNode;
  if (dataState === "loading" || dataState === "error")
    body = <LoadState state={dataState} what="schema" />;
  else if (view === "graph")
    body = (
      <Card className="grow items-center justify-center p-10">
        <p className="text-foreground-muted text-sm">
          Stand-in: the existing graph of the schema, unchanged.
        </p>
      </Card>
    );
  else if (staged && stagedStatus === "applied")
    body = (
      <EmptyState
        icon="mdi:check-circle-outline"
        tone="success"
        title="The staged schema change is applied"
        actions={
          <button type="button" onClick={() => setView("list")} className={LINK}>
            View List
          </button>
        }
      >
        <Mono>{APPLIED_CHANGE.name}</Mono> became revision {pad(APPLIED_CHANGE.version ?? 0)}, so
        List shows the schema with it.
      </EmptyState>
    );
  else if (staged && !hasStaged)
    body = (
      <EmptyState
        icon="mdi:tray-arrow-down"
        title="No staged schema change on this branch"
        actions={
          <>
            <CommandLine command={STAGE_COMMAND(BRANCH)} />
            <button type="button" onClick={() => setView("list")} className={LINK}>
              View List
            </button>
          </>
        }
      >
        Stage a schema file to view the schema it would produce, kind by kind.
      </EmptyState>
    );
  else
    body = (
      <>
        {staged && (
          <InlineMessage
            tone="info"
            title={
              stagedStatus === "applying"
                ? "You are viewing the schema after the staged change. Infrahub is applying it."
                : "You are viewing the schema after the staged change. It is not applied."
            }
            action={
              <NavLink
                to={{ scene: "Branch: Schema changes", changeId: STAGED_CHANGE.id }}
                className="text-sm"
              >
                View the impact on data
              </NavLink>
            }
          >
            <Mono>{STAGED_CHANGE.name}</Mono>, staged <When date={STAGED_CHANGE.createdAt} />.
          </InlineMessage>
        )}
        <div
          className="flex min-h-0 grow flex-col gap-3 lg:flex-row"
          style={{ "--list-width": "320px" } as CSSProperties}
        >
          {kindList}
          {kindDetails}
        </div>
      </>
    );

  return (
    <Content.Card className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
        <Col className="min-w-0 grow gap-0.5">
          <Row className="items-center gap-2">
            <h1 className="font-bold text-xl">Schema</h1>
            <Badge className="text-sm">{SCHEMA_KIND_COUNT}</Badge>
          </Row>
          <span className="truncate text-foreground-muted text-sm" title={BRANCH}>
            {BRANCH} · revision {pad(revision?.version ?? 0)}
          </span>
        </Col>
        <ToggleGroup
          label="Schema views"
          active={view}
          onSelect={(id) => setView(id as Viewer)}
          items={[
            { id: "list", label: "List", icon: "mdi:format-list-bulleted", live: true },
            { id: "graph", label: "Graph", icon: "mdi:graph", live: true },
            {
              id: "staged",
              label: <>Staged {hasStaged && <Badge variant="blue">1</Badge>}</>,
              icon: "mdi:tray-arrow-down",
              live: true,
            },
          ]}
        />
      </header>
      <Card variant="panel" className="m-1 flex min-h-0 grow flex-col gap-3 overflow-auto p-3">
        {body}
      </Card>
    </Content.Card>
  );
}

/* ------------------------------------------------------------------ proposed change */

function MergeHeader({ mode, hasStaged }: { mode: MergeMode; hasStaged: boolean }) {
  const steps = REPLAY.length;
  const before = FAIL_INDEX;
  const after = steps - FAIL_INDEX - 1;
  const afterText = after === 1 ? "the one after it" : `the ${after} after it`;
  return (
    <RecordHeader
      label="Merge into main"
      title={
        <span className="flex flex-wrap items-center gap-2 font-semibold text-sm">
          Main
          <VersionChip version={PROPOSED_CHANGE.mainVersion} />
          <Icon icon="mdi:arrow-right" aria-hidden="true" />
          <VersionChip version={PROPOSED_CHANGE.mainVersion + steps} />
          after the merge
        </span>
      }
      status={<Status status={mode === "rolled back" ? "rolled back" : "would fail"} />}
      facts={
        <>
          <span>
            {steps} schema changes from this branch, applied after the data changes, in version
            order from {pad(REPLAY[0]?.version ?? 0)}
            {hasStaged && " ·"}
          </span>
          {hasStaged && (
            <NavLink
              to={{
                scene:
                  mode === "rolled back"
                    ? "Proposed change: merge rolled back"
                    : "Proposed change: Schema changes",
                changeId: STAGED_CHANGE.id,
              }}
            >
              1 staged schema change, not merged
            </NavLink>
          )}
        </>
      }
      actions={
        <Button size="sm" variant="outline">
          <Icon icon="mdi:refresh" aria-hidden="true" />
          Check again
        </Button>
      }
    >
      {mode === "rolled back" ? (
        <InlineMessage
          tone="danger"
          title={`The merge failed at ${FAILING_VERSION} and was rolled back`}
        >
          Started <When date={MERGE_ATTEMPT.at} />. The {before} schema changes before it were
          rolled back and {afterText} did not run, so main is still at{" "}
          {pad(PROPOSED_CHANGE.mainVersion)}. Its details are open below.
        </InlineMessage>
      ) : (
        <InlineMessage
          tone="danger"
          title={`${FAILING_VERSION} would fail against the current main`}
        >
          Checked <When date={PC_CHECK.checkedAt} />. The {before} schema changes before it pass,
          and {afterText} is not checked. Its details are open below.
        </InlineMessage>
      )}
    </RecordHeader>
  );
}

function ProposedChangeView({
  mode,
  stagedStatus,
  impactState,
  dataState,
  listWidth,
}: {
  mode: MergeMode;
  stagedStatus: StagedStatus;
  impactState: ImpactState;
  dataState: DataState;
  listWidth: number;
}) {
  const { focus } = useContext(Nav);
  const [section, setSection] = useState("changes");
  const loaded = dataState !== "loading" && dataState !== "error" && dataState !== "empty";
  const stagedNow = dataState !== "empty" && stagedStatus !== "applied" ? stagedStatus : null;
  return (
    <ProposedChangePage active="schema" schemaCount={loaded ? REPLAY.length : undefined}>
      <Card variant="panel" className="m-1">
        <FakeTabs
          label="Schema sections"
          active={section}
          onSelect={setSection}
          tabs={[
            {
              id: "changes",
              label: "Schema changes",
              count: loaded ? REPLAY.length : undefined,
              live: true,
            },
            { id: "diff", label: "Diff", live: true },
          ]}
        />
        <div className="flex flex-col gap-3 border-t p-3">
          {section === "changes" && loaded && <MergeHeader mode={mode} hasStaged={!!stagedNow} />}
          {section === "changes" && (
            <SchemaChangesView
              key={`${mode}-${dataState}-${stagedStatus}-${impactState}`}
              branch={BRANCH}
              history={BRANCH_HISTORY}
              initialIds={[focus.changeId, addressValue("pc_change"), PC_CHECK.failingChangeId]}
              addressKey="pc_change"
              dataState={dataState}
              listWidth={listWidth}
              merge={mode}
              staged={
                stagedNow
                  ? {
                      status: stagedNow,
                      note: stagedNote(stagedNow, impactState),
                      details: (
                        <StagedDetails
                          impactState={impactState}
                          dataState={dataState}
                          status={stagedNow}
                          inProposedChange
                        />
                      ),
                    }
                  : undefined
              }
              header={
                <span className="flex flex-col">
                  <span>Schema changes of the branch</span>
                  <span className="font-normal text-foreground-muted text-xs">
                    Newest first, with the version each one gets on main
                  </span>
                </span>
              }
            />
          )}
          {section === "diff" && (
            <Card>
              <NodeDiffStandIn />
            </Card>
          )}
        </div>
      </Card>
    </ProposedChangePage>
  );
}

/* ------------------------------------------------------------------ entry */

function Screen({
  scene,
  impactState,
  dataState,
  listWidth,
  stagedStatus,
}: Omit<Props, "setScene" | "toggleStyle">) {
  const merge = { stagedStatus, impactState, dataState, listWidth };
  switch (scene) {
    case "Branch: Details":
      return <BranchDetailsView dataState={dataState} stagedStatus={stagedStatus} />;
    case "Schema viewer":
      return <SchemaViewerView stagedStatus={stagedStatus} dataState={dataState} />;
    case "Proposed change: Schema changes":
      return <ProposedChangeView mode="review" {...merge} />;
    case "Proposed change: merge rolled back":
      return <ProposedChangeView mode="rolled back" {...merge} />;
    default:
      return (
        <BranchSchemaTab
          onMain={scene === "Main: Schema changes"}
          stagedStatus={stagedStatus}
          impactState={impactState}
          dataState={dataState}
          listWidth={listWidth}
        />
      );
  }
}

export function CollapsibleSectionsRev01({
  setScene,
  toggleStyle,
  sectionDefault,
  ...props
}: Props & { sectionDefault: SectionDefault }) {
  const [nav, setNav] = useState<{ target: Target | null; n: number }>({ target: null, n: 0 });
  const go = (target: Target) => {
    setNav((prev) => ({ target, n: prev.n + 1 }));
    setScene(target.scene);
  };
  // A link's selection applies only to the screen it opened, not to one picked later in the panel.
  const focus = nav.target?.scene === props.scene ? nav.target : {};
  const root = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>();
  // The app gives a page the window's height; the design panel's pane does not, so the page takes the pane's.
  useLayoutEffect(() => {
    const pane = root.current?.closest<HTMLElement>(".djh-pane");
    if (!pane) return;
    const measure = () => setHeight(pane.clientHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(pane);
    return () => observer.disconnect();
  }, []);
  // Layout effects run before the passive effect that scrolls a linked kind into view.
  useLayoutEffect(() => {
    if (nav.n === 0) return;
    for (let el = root.current?.parentElement; el; el = el.parentElement) el.scrollTop = 0;
  }, [nav.n]);
  return (
    <Nav.Provider value={{ go, focus }}>
      <IdentifierFont.Provider value="app">
        <SectionDefaultContext.Provider value={sectionDefault}>
          <ToggleStyleContext.Provider value={toggleStyle}>
            <div ref={root} className="flex flex-col" style={{ height }}>
              <Screen key={`${props.scene}-${nav.n}`} {...props} />
            </div>
          </ToggleStyleContext.Provider>
        </SectionDefaultContext.Provider>
      </IdentifierFont.Provider>
    </Nav.Provider>
  );
}
