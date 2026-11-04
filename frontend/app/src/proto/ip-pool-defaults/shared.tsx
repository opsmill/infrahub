import {
  Button,
  Card,
  ListBox,
  ListBoxItem,
  Menu,
  MenuItem,
  MenuSection,
  MenuTrigger,
  Popover,
  Tooltip,
} from "@infrahub/ui";
import { ChevronDownIcon, PencilLineIcon, Trash2Icon } from "lucide-react";
import React from "react";
import { Button as AriaButton, DialogTrigger, Text } from "react-aria-components";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { CopyToClipboardMenuItem } from "@/shared/components/menu/copy-to-clipboard-menu-item";
import MultipleProgressBar from "@/shared/components/stats/multiple-progress-bar";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { formatUsagePercent } from "@/entities/resource-manager/ui/number-pool/details/number-pool-usage-bar";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { SchemaViewerModal } from "@/entities/schema/ui/schema-viewer-modal";

import type { ProtoPool, ResourcePrefix } from "./data";

const REFRESHED_QUERY_KEYS = [resourceManagerQueryKeys.all];

export const schemaLinkStyle =
  "cursor-pointer rounded-md font-medium underline decoration-dotted outline-none data-hovered:decoration-solid data-focus-visible:ring-2 data-focus-visible:ring-ring-halo";

export const DEFAULTS_HELP = "Used when an allocation request does not set its own value.";

interface KindReferenceProps {
  kind: string;
  className?: string;
}

export function KindReference({ kind, className }: KindReferenceProps) {
  const { schema } = useSchema(kind);

  if (!schema) return <span className={classNames("font-medium", className)}>{kind}</span>;

  return (
    <DialogTrigger>
      <AriaButton className={classNames(schemaLinkStyle, className)}>{kind}</AriaButton>
      <SchemaViewerModal schema={schema} />
    </DialogTrigger>
  );
}

export interface DefaultEntry {
  label: string;
  value: React.ReactNode | null;
  fallback: string;
  fallbackPhrase: string;
}

const MEMBER_TYPE_LABELS = { prefix: "Prefix", address: "Address" } as const;

const REQUEST_MUST_SET = "Request must set it";
const NO_DEFAULT = "has no default";

export function getDefaultEntries(pool: ProtoPool): DefaultEntry[] {
  const { prefixLength, createdKind, memberType } = pool.defaults;
  const length = prefixLength === null ? null : <span className="tabular-nums">/{prefixLength}</span>;
  const kind = createdKind === null ? null : <KindReference kind={createdKind} />;

  if (pool.poolKind === "address") {
    return [
      { label: "Address kind", value: kind, fallback: REQUEST_MUST_SET, fallbackPhrase: NO_DEFAULT },
      {
        label: "Prefix length",
        value: length,
        fallback: "Same as resource prefix",
        fallbackPhrase: "follows the resource prefix",
      },
    ];
  }

  return [
    { label: "Prefix kind", value: kind, fallback: REQUEST_MUST_SET, fallbackPhrase: NO_DEFAULT },
    { label: "Prefix length", value: length, fallback: REQUEST_MUST_SET, fallbackPhrase: NO_DEFAULT },
    {
      label: "Member type",
      value: memberType === null ? null : MEMBER_TYPE_LABELS[memberType],
      fallback: MEMBER_TYPE_LABELS.prefix,
      fallbackPhrase: `defaults to ${MEMBER_TYPE_LABELS.prefix}`,
    },
  ];
}

export function NotSet({ fallback }: { fallback: string }) {
  return <span className="text-foreground-muted">{fallback}</span>;
}

interface DefaultsListProps {
  pool: ProtoPool;
  className?: string;
}

export function DefaultsList({ pool, className }: DefaultsListProps) {
  return (
    <dl className={classNames("grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm", className)}>
      {getDefaultEntries(pool).map(({ label, value, fallback }) => (
        <React.Fragment key={label}>
          <dt className="text-foreground-muted">{label}</dt>
          <dd className="min-w-0 truncate text-right">{value ?? <NotSet fallback={fallback} />}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

export function NamespaceLine({ pool }: { pool: ProtoPool }) {
  return (
    <Row className="min-w-0 gap-1.5 text-sm">
      <span className="shrink-0 text-foreground-muted">In namespace</span>
      <Link to="/ipam" className="min-w-0 truncate font-medium">
        {pool.namespace}
      </Link>
    </Row>
  );
}

function PoolId({ id }: { id: string }) {
  return (
    <Row className="h-8 min-w-0 gap-1 text-sm">
      <span className="shrink-0">ID</span>
      <span className="min-w-0 truncate font-mono text-foreground-muted text-xs">{id}</span>
      <CopyToClipboardButton data={id} aria-label="Copy ID" />
    </Row>
  );
}

const NOT_IN_PROTOTYPE = "Not part of this prototype";

function ActionsMenu({ pool }: { pool: ProtoPool }) {
  return (
    <MenuTrigger>
      <Button variant="outline" size="sm" className="shrink-0">
        Actions <ChevronDownIcon className="size-3.5" />
      </Button>
      <Popover placement="bottom end">
        <Menu>
          <MenuSection title="Actions">
            <CopyToClipboardMenuItem textToCopy={pool.id} textValue="Copy ID">
              Copy ID
            </CopyToClipboardMenuItem>
          </MenuSection>
          <MenuSection title="Manage">
            <MenuItem isDisabled tooltip={NOT_IN_PROTOTYPE} textValue="Edit">
              <PencilLineIcon />
              <span>Edit</span>
            </MenuItem>
            <MenuItem isDisabled tooltip={NOT_IN_PROTOTYPE} className="text-danger" textValue="Delete">
              <Trash2Icon />
              <span>Delete</span>
            </MenuItem>
          </MenuSection>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}

interface PoolHeaderProps {
  pool: ProtoPool;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}

export function PoolHeader({ pool, actions, children }: PoolHeaderProps) {
  return (
    <header className="px-3 py-2 text-sm">
      <Row className="mb-4 items-start">
        <Col className="min-w-0 grow gap-0">
          <h1 className="min-w-0 truncate font-bold text-xl" title={pool.name}>
            {pool.name}
          </h1>
          {pool.description && <p className="text-pretty text-foreground-muted">{pool.description}</p>}
        </Col>
        <PoolId id={pool.id} />
        <RefreshButton queryKeys={REFRESHED_QUERY_KEYS} />
        {actions}
        <ActionsMenu pool={pool} />
      </Row>
      {children}
    </header>
  );
}

function UsageTooltipMessage({ title, value }: { title: string; value: string }) {
  return (
    <Col className="gap-0.5">
      <span className="text-white/70 text-xxs">{title}</span>
      <span className="tabular-nums">{value}</span>
    </Col>
  );
}

function UsageBar({ resource }: { resource: ResourcePrefix }) {
  return (
    <Row>
      <MultipleProgressBar
        className="h-1.5"
        aria-label="Usage"
        elements={[
          {
            value: resource.utilizationDefaultBranch,
            color: "var(--accent-strong)",
            tooltip: (
              <UsageTooltipMessage
                title="Default branch"
                value={formatUsagePercent(resource.utilizationDefaultBranch)}
              />
            ),
          },
          {
            value: resource.utilizationBranches,
            color: "color-mix(in oklch, var(--accent-strong) 45%, transparent)",
            tooltip: (
              <UsageTooltipMessage
                title="Other branches only"
                value={formatUsagePercent(resource.utilizationBranches)}
              />
            ),
          },
        ]}
      />
      <Tooltip
        nonInteractiveTrigger
        message={<UsageTooltipMessage title="Used" value={formatUsagePercent(resource.utilization)} />}
      >
        <span className="w-11 shrink-0 text-right font-medium text-foreground text-xs tabular-nums">
          {formatUsagePercent(resource.utilization)}
        </span>
      </Tooltip>
    </Row>
  );
}

interface ResourcePrefixesCardProps {
  pool: ProtoPool;
  selectedId: string;
  onSelect: (id: string) => void;
}

function ResourcePrefixesCard({ pool, selectedId, onSelect }: ResourcePrefixesCardProps) {
  return (
    <Card>
      <div className="px-3 pt-2 pb-1 font-medium text-foreground-muted text-sm">Resource prefixes</div>
      <ListBox
        aria-label="Resource prefixes"
        selectionMode="single"
        selectionIndicator="highlight"
        disallowEmptySelection
        selectedKeys={[selectedId]}
        onSelectionChange={(keys) => {
          const [key] = [...keys];
          if (key !== undefined) onSelect(String(key));
        }}
        items={pool.resources}
      >
        {(resource) => (
          <ListBoxItem
            id={resource.id}
            textValue={resource.prefix}
            className="flex-col items-stretch gap-1.5 rounded-xl px-2.5 py-2"
          >
            <Row className="justify-between gap-3">
              <Text slot="label" className="min-w-0 truncate font-medium tabular-nums">
                {resource.prefix}
              </Text>
              <Text slot="description" className="shrink-0 text-foreground-muted text-xs">
                Weight {resource.weight}
              </Text>
            </Row>
            <UsageBar resource={resource} />
          </ListBoxItem>
        )}
      </ListBox>
    </Card>
  );
}

const columnStyle = "h-8 px-3 text-left font-medium text-foreground-muted text-xs";
const cellStyle = "h-9 px-3 text-sm";

function AllocatedCard({ pool, resource }: { pool: ProtoPool; resource: ResourcePrefix }) {
  const noun = pool.poolKind === "address" ? "addresses" : "prefixes";
  const rows =
    resource.utilization === 0
      ? []
      : pool.allocated.slice(0, Math.max(3, Math.round((pool.allocated.length * resource.utilization) / 100)));

  return (
    <Card className="max-h-full min-w-0 grow overflow-hidden">
      <Row className="h-11 shrink-0 gap-2 border-b px-3">
        <span className="font-medium">Allocated {noun}</span>
        <span className="text-foreground-muted text-sm tabular-nums">{rows.length}</span>
        <span className="min-w-0 truncate text-foreground-muted text-sm">in {resource.prefix}</span>
      </Row>

      {rows.length === 0 ? (
        <Col className="items-center gap-1.5 px-6 py-16 text-center">
          <p className="font-medium">No {noun} in {resource.prefix} yet</p>
          <p className="max-w-sm text-pretty text-foreground-muted text-sm">
            The pool allocates from this resource prefix once the others with a higher weight are full.
          </p>
        </Col>
      ) : (
        <div className="min-h-0 overflow-auto">
          <table className="w-full table-fixed border-collapse">
            <thead className="sticky top-0 bg-content">
              <tr className="border-b">
                <th className={classNames(columnStyle, "w-56")}>{pool.poolKind === "address" ? "Address" : "Prefix"}</th>
                <th className={columnStyle}>Identifier</th>
                <th className={classNames(columnStyle, "w-36")}>Kind</th>
                <th className={classNames(columnStyle, "w-24")}>Branch</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-border/50 border-b">
                  <td className={classNames(cellStyle, "font-medium tabular-nums")}>
                    <Link to="#" className="no-underline hover:underline">
                      {row.value}
                    </Link>
                  </td>
                  <td className={classNames(cellStyle, "truncate font-mono text-xs")} title={row.identifier ?? undefined}>
                    {row.identifier ?? <span className="font-sans text-foreground-muted text-sm">None</span>}
                  </td>
                  <td className={classNames(cellStyle, "truncate text-foreground-muted")}>{row.kind}</td>
                  <td className={classNames(cellStyle, "text-foreground-muted")}>{row.branch}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

interface PoolPageProps {
  pool: ProtoPool;
  header: React.ReactNode;
  aside?: React.ReactNode;
}

export function PoolPage({ pool, header, aside }: PoolPageProps) {
  const [selectedId, setSelectedId] = React.useState(pool.resources[0]!.id);
  const resource = pool.resources.find(({ id }) => id === selectedId) ?? pool.resources[0]!;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Content.Card className="grow overflow-hidden">
        {header}
        <Row className="min-h-0 grow items-start px-2 pb-2">
          <Col className="min-h-0 w-80 shrink-0 gap-2">
            {aside}
            <ResourcePrefixesCard pool={pool} selectedId={resource.id} onSelect={setSelectedId} />
          </Col>
          <AllocatedCard pool={pool} resource={resource} />
        </Row>
      </Content.Card>
    </div>
  );
}
