// PROTOTYPE design-jam instance-badge
import { Tooltip } from "@infrahub/ui";
import type { ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

import type { KnobValue } from "../../design-history-panel";
import { PRESET_STYLE, type Preset, readSharedKnobs } from "../../fixtures";
import { InstanceBadge, InstanceBar } from "../../instance-badge";
import { FakeLogin, FakeShell } from "../../shell";

/** The collapsed sidebar keeps a dot in the instance color; the tooltip carries the label. */
function InstanceDot({ label, color }: { label: string; color: Preset | null }) {
  return (
    <Tooltip message={label} placement="right" nonInteractiveTrigger>
      <span
        role="img"
        className="flex h-6 items-center justify-center"
        aria-label={`Instance ${label}`}
      >
        <span className={classNames("size-2.5 rounded-full", PRESET_STYLE[color ?? "gray"].bar)} />
      </span>
    </Tooltip>
  );
}

export function render(knobs: Record<string, KnobValue>): ReactNode {
  const k = readSharedKnobs(knobs);
  const bar = <InstanceBar color={k.color} height={k.barHeight} />;

  if (k.screen === "login") {
    return (
      <FakeLogin
        dark={k.dark}
        topBar={bar}
        belowLogo={<InstanceBadge label={k.label} color={k.color} />}
      />
    );
  }

  const brand = !k.label ? null : k.collapsed ? (
    <InstanceDot label={k.label} color={k.color} />
  ) : (
    <div className="flex px-0.75">
      <InstanceBadge label={k.label} color={k.color} className="max-w-full" />
    </div>
  );

  return <FakeShell collapsed={k.collapsed} dark={k.dark} topBar={bar} sidebarBrand={brand} />;
}
