// PROTOTYPE design-jam instance-badge
import type { ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

import type { KnobValue } from "../../design-history-panel";
import { PRESET_STYLE, readSharedKnobs, readStripHeight, stripHeightClass } from "../../fixtures";
import { InstanceBar } from "../../instance-badge";
import { FakeLogin, FakeShell } from "../../shell";

type StripProps = {
  label: string;
  colorClass: string;
  height: number;
};

function BannerStrip({ label, colorClass, height }: StripProps) {
  return (
    <div
      className={classNames(
        "flex w-full shrink-0 items-center justify-center",
        stripHeightClass(height),
        colorClass
      )}
    >
      <span className="truncate px-3 font-semibold text-xxs uppercase tracking-wider" title={label}>
        {label}
      </span>
    </div>
  );
}

export function render(knobs: Record<string, KnobValue>): ReactNode {
  const k = readSharedKnobs(knobs);
  const stripHeight = readStripHeight(knobs);

  const top = k.label ? (
    <BannerStrip
      label={k.label}
      colorClass={PRESET_STYLE[k.color ?? "gray"].solid}
      height={stripHeight}
    />
  ) : (
    <InstanceBar color={k.color} height={k.barHeight} />
  );

  if (k.screen === "login") {
    return <FakeLogin dark={k.dark} topBar={top} />;
  }

  return <FakeShell collapsed={k.collapsed} dark={k.dark} topBar={top} />;
}
