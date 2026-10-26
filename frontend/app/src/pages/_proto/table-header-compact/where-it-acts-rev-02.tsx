// PROTOTYPE design-jam table-header-compact — "Where it acts" rev 2; a frozen copy, never import it from rev 1.
import { Button, Popover, PopoverTrigger, Tooltip } from "@infrahub/ui";
import {
  BracesIcon,
  ChevronDownIcon,
  Columns3Icon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
} from "lucide-react";

import { Col, Row } from "@/shared/components/container";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { classNames } from "@/shared/utils/common";

import { RELATIONSHIP_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { ColumnsEditor } from "@/entities/nodes/columns/ui/columns-editor";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";

import { PageCard, Tabs } from "./chrome";
import { type ObjectKey, useRelationshipTab } from "./data";

type Tab = ReturnType<typeof useRelationshipTab>;

function AddButton({ tab }: { tab: Tab }) {
  const label = tab.parentSchema?.relationships?.find(
    (r) => r.name === tab.target.relationshipName
  )?.label;
  const { isAllowed, message } = tab.permission?.create ?? { isAllowed: false, message: "" };
  return (
    <Tooltip message={message ?? `Add ${label}`}>
      <Button isDisabledAndFocusable={!isAllowed} size="sm">
        <PlusIcon aria-hidden="true" /> Add {label}
      </Button>
    </Tooltip>
  );
}

function Header({ title, tab }: { title: string; tab: Tab }) {
  return (
    <Row className="items-center gap-2 px-4 py-3">
      <h1 className="min-w-0 truncate font-bold text-xl">{title}</h1>
      <Row className="ml-auto shrink-0 items-center gap-2">
        <AddButton tab={tab} />
        <Button variant="outline" size="sm" shape="square" aria-label="Refresh">
          <RefreshCwIcon />
        </Button>
        <Button variant="outline" size="sm">
          <PencilIcon /> Edit
        </Button>
        <Button variant="outline" size="sm">
          <BracesIcon /> Schema
        </Button>
        <Button variant="outline" size="sm">
          Actions <ChevronDownIcon />
        </Button>
      </Row>
    </Row>
  );
}

function ColumnsHeaderCell({ tab }: { tab: Tab }) {
  const { customizedColumnCount } = useColumnVisibility(
    tab.relationshipSchema!,
    RELATIONSHIP_COLUMN_SURFACE
  );
  const changed = customizedColumnCount > 0;
  const message = changed ? `Columns · ${customizedColumnCount} changed` : "Columns";
  return (
    <div
      className={classNames(
        cellsStyle,
        cellHeaderStyle,
        "right-0 z-10 -ml-px size-10 justify-center border-l p-0"
      )}
    >
      <PopoverTrigger>
        <Tooltip message={message}>
          <Button
            variant="ghost"
            size="xs"
            shape="square"
            aria-label={message}
            className="relative"
          >
            <Columns3Icon />
            {changed && (
              <span
                aria-hidden="true"
                className="absolute top-1 right-1 size-1.5 rounded-full bg-custom-blue-600"
              />
            )}
          </Button>
        </Tooltip>
        <Popover placement="bottom end">
          <ColumnsEditor schema={tab.relationshipSchema!} surface={RELATIONSHIP_COLUMN_SURFACE} />
        </Popover>
      </PopoverTrigger>
    </div>
  );
}

export function WhereItActsRev02({
  objectKey,
  denyPermission,
}: {
  objectKey: ObjectKey;
  denyPermission: boolean;
}) {
  const tab = useRelationshipTab(objectKey, denyPermission);
  if (!tab.relationshipSchema || !tab.parentSchema) return null;

  const title = (tab.parentData as { display_label?: string } | undefined)?.display_label ?? "…";

  return (
    <PageCard>
      <Header title={title} tab={tab} />
      <Tabs
        tabs={tab.target.tabs}
        active={tab.target.activeTab}
        counts={{ [tab.target.activeTab]: tab.count }}
      />
      <Col className="gap-0 overflow-hidden">
        <Table tab={tab} />
      </Col>
    </PageCard>
  );
}

function Table({ tab }: { tab: Tab }) {
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
        columns={tab.buildColumns(() => <ColumnsHeaderCell tab={tab} />)}
        columnVisibility={columnVisibility}
        count={tab.count}
        data={tab.rows}
        isLoading={tab.isLoading}
        renderEmpty={() => <ObjectTableEmpty schema={tab.relationshipSchema!} />}
      />
    </InfiniteScroll>
  );
}
