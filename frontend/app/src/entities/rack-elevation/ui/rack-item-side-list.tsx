import { Button } from "@infrahub/ui";

import { Col } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import type { RackElevationItem } from "@/entities/rack-elevation/domain/model/rack-elevation";

const NEUTRAL_SWATCH_COLOR = "#9ca3af";

export interface RackItemSideListProps {
  title: string;
  emptyMessage: string;
  items: RackElevationItem[];
  selectedItemId: string | null;
  onItemPress: (item: RackElevationItem) => void;
  "data-testid": string;
}

export function RackItemSideList({
  title,
  emptyMessage,
  items,
  selectedItemId,
  onItemPress,
  "data-testid": testId,
}: RackItemSideListProps) {
  return (
    <Col className="gap-1" data-testid={testId}>
      <h3 className="font-semibold text-sm">
        {title} ({items.length})
      </h3>
      {items.length === 0 && <p className="text-foreground-muted text-xs">{emptyMessage}</p>}
      {items.map((item) => (
        <Button
          key={item.id}
          variant="outline"
          size="sm"
          className={classNames(
            "justify-start gap-2 text-left",
            item.id === selectedItemId && "border-blue-600 ring-2 ring-blue-600"
          )}
          data-testid={`rack-item-${item.display_label}`}
          onPress={() => onItemPress(item)}
        >
          <span
            className="size-3 shrink-0 rounded-full border border-border-strong"
            style={{ backgroundColor: item.color ?? NEUTRAL_SWATCH_COLOR }}
          />
          <span className="min-w-0 truncate">{item.label}</span>
          <span className="ml-auto shrink-0 text-foreground-muted text-xs">
            {item.type_display_label ?? "No type"}
          </span>
        </Button>
      ))}
    </Col>
  );
}
