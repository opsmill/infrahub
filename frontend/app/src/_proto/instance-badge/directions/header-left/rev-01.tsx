// PROTOTYPE design-jam instance-badge
import type { ReactNode } from "react";

import type { KnobValue } from "../../design-history-panel";
import { readSharedKnobs } from "../../fixtures";
import { InstanceBadge, InstanceBar } from "../../instance-badge";
import { FakeLogin, FakeShell } from "../../shell";

export function render(knobs: Record<string, KnobValue>): ReactNode {
  const k = readSharedKnobs(knobs);
  const bar = <InstanceBar color={k.color} height={k.barHeight} />;
  const badge = <InstanceBadge label={k.label} color={k.color} />;

  if (k.screen === "login") {
    return <FakeLogin dark={k.dark} topBar={bar} aboveLogo={badge} />;
  }

  return <FakeShell collapsed={k.collapsed} dark={k.dark} topBar={bar} headerLeading={badge} />;
}
