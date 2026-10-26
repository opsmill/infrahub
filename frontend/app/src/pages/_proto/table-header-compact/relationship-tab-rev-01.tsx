// PROTOTYPE design-jam table-header-compact — rev 1 of every direction for the relationship tab toolbar.
import { Button, Popover, PopoverTrigger, Tooltip } from "@infrahub/ui";
import { Columns3Icon, PlusIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Col, Row } from "@/shared/components/container";
import { DataTable } from "@/shared/components/table/data-table";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { classNames } from "@/shared/utils/common";

import { RELATIONSHIP_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { ColumnsEditor } from "@/entities/nodes/columns/ui/columns-editor";
import { ColumnsPicker } from "@/entities/nodes/columns/ui/columns-picker";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";

import { ObjectHeader, PageCard, Tabs } from "./chrome";
import { type ObjectKey, useRelationshipTab } from "./data";

export type Direction = "baseline" | "one-row" | "tab-strip" | "where-it-acts";

type Tab = ReturnType<typeof useRelationshipTab>;

function AddButton({ tab, compact = false }: { tab: Tab; compact?: boolean }) {
  const label = tab.parentSchema?.relationships?.find(
    (r) => r.name === tab.target.relationshipName
  )?.label;
  const { isAllowed, message } = tab.permission?.create ?? { isAllowed: false, message: "" };
  return (
    <Tooltip message={message ?? `Add ${label}`}>
      <Button isDisabledAndFocusable={!isAllowed} size={compact ? "xs" : "sm"}>
        <PlusIcon aria-hidden="true" /> Add {label}
      </Button>
    </Tooltip>
  );
}

function ColumnsIconHeader({ tab }: { tab: Tab }) {
  const { customizedColumnCount } = useColumnVisibility(
    tab.relationshipSchema!,
    RELATIONSHIP_COLUMN_SURFACE
  );
  return (
    <div
      className={classNames(
        cellsStyle,
        cellHeaderStyle,
        "right-0 z-10 -ml-px size-10 justify-center border-l p-0"
      )}
    >
      <PopoverTrigger>
        <Button
          variant="ghost"
          size="xs"
          shape="square"
          aria-label="Columns"
          className={customizedColumnCount > 0 ? "text-custom-blue-600" : undefined}
        >
          <Columns3Icon />
        </Button>
        <Popover placement="bottom end">
          <ColumnsEditor schema={tab.relationshipSchema!} surface={RELATIONSHIP_COLUMN_SURFACE} />
        </Popover>
      </PopoverTrigger>
    </div>
  );
}

function Table({ tab, actionsHeader }: { tab: Tab; actionsHeader?: () => ReactNode }) {
  const { columnVisibility } = useColumnVisibility(
    tab.relationshipSchema!,
    RELATIONSHIP_COLUMN_SURFACE
  );
  return (
    <InfiniteScroll
      scrollX
      className="bg-table-frame"
      hasNextPage={tab.hasNextPage}
      onLoadMore={tab.fetchNextPage}
    >
      <DataTable
        columns={tab.buildColumns(actionsHeader)}
        columnVisibility={columnVisibility}
        count={tab.count}
        data={tab.rows}
        isLoading={tab.isLoading}
        renderEmpty={() => <ObjectTableEmpty schema={tab.relationshipSchema!} />}
      />
    </InfiniteScroll>
  );
}

export function RelationshipTabRev01({
  direction,
  objectKey,
  denyPermission,
}: {
  direction: Direction;
  objectKey: ObjectKey;
  denyPermission: boolean;
}) {
  const tab = useRelationshipTab(objectKey, denyPermission);
  if (!tab.relationshipSchema || !tab.parentSchema) return null;

  const title = (tab.parentData as { display_label?: string } | undefined)?.display_label ?? "…";
  const counts = { [tab.target.activeTab]: tab.count };
  const columnsPicker = (
    <ColumnsPicker schema={tab.relationshipSchema} surface={RELATIONSHIP_COLUMN_SURFACE} />
  );

  if (direction === "baseline") {
    return (
      <PageCard>
        <ObjectHeader title={title} />
        <Tabs tabs={tab.target.tabs} active={tab.target.activeTab} counts={counts} />
        <Col className="gap-0 overflow-hidden">
          <Row className="justify-end p-2">
            <AddButton tab={tab} />
          </Row>
          <Row className="justify-end p-2">{columnsPicker}</Row>
          <Table tab={tab} />
        </Col>
      </PageCard>
    );
  }

  if (direction === "one-row") {
    return (
      <PageCard>
        <ObjectHeader title={title} />
        <Tabs tabs={tab.target.tabs} active={tab.target.activeTab} counts={counts} />
        <Col className="gap-0 overflow-hidden">
          <Row className="items-center p-2">
            {columnsPicker}
            <div className="ml-auto">
              <AddButton tab={tab} />
            </div>
          </Row>
          <Table tab={tab} />
        </Col>
      </PageCard>
    );
  }

  if (direction === "tab-strip") {
    return (
      <PageCard>
        <ObjectHeader title={title} />
        <Tabs
          tabs={tab.target.tabs}
          active={tab.target.activeTab}
          counts={counts}
          trailing={
            <>
              {columnsPicker}
              <AddButton tab={tab} compact />
            </>
          }
        />
        <Col className="gap-0 overflow-hidden">
          <Table tab={tab} />
        </Col>
      </PageCard>
    );
  }

  return (
    <PageCard>
      <ObjectHeader title={title} actions={<AddButton tab={tab} />} />
      <Tabs tabs={tab.target.tabs} active={tab.target.activeTab} counts={counts} />
      <Col className="gap-0 overflow-hidden">
        <Table tab={tab} actionsHeader={() => <ColumnsIconHeader tab={tab} />} />
      </Col>
    </PageCard>
  );
}
