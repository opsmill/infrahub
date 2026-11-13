// PROTOTYPE design-jam account-settings — direction "side-nav", rev 2. Frozen.

import { Col } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { classNames } from "@/shared/utils/common";

import type { KnobValue } from "../design-history-panel";
import {
  IdentityHeader,
  resolveSection,
  SectionBody,
  type SectionDef,
  SectionHeader,
  sectionsFor,
  toScenario,
  useSection,
} from "../sections-v2";

export function SideNavRev02({ knobs }: { knobs: Record<string, KnobValue> }) {
  const s = toScenario(knobs);
  const defs = sectionsFor(s);
  const [asked, go] = useSection("profile");
  const section = resolveSection(asked, defs);
  const active = defs.find((d) => d.id === section) as SectionDef;
  const groups = ["Personal", "Administration"] as const;

  return (
    <Content.Card className="flex h-full flex-col">
      <Content.CardTitle title="Account settings" />

      <div className="flex min-h-0 flex-1">
        <nav
          aria-label="Account settings"
          className="flex w-60 shrink-0 flex-col gap-4 border-r p-3"
        >
          <div className="px-1 pb-1">
            <IdentityHeader s={s} compact />
          </div>
          {groups.map((g) => {
            const items = defs.filter((d) => d.group === g);
            if (items.length === 0) return null;
            return (
              <Col key={g} className="gap-0.5">
                <div className="px-2.5 pb-1 font-medium text-foreground-muted text-xs">{g}</div>
                {items.map((d) => {
                  const isActive = d.id === section;
                  return (
                    <a
                      key={d.id}
                      href={`?section=${d.id}`}
                      aria-current={isActive ? "page" : undefined}
                      onClick={(e) => {
                        e.preventDefault();
                        go(d.id);
                      }}
                      className={classNames(
                        "flex items-center gap-2 rounded-lg px-2.5 py-2 font-medium text-sm outline-hidden",
                        "focus-visible:ring-2 focus-visible:ring-ring-halo",
                        isActive
                          ? "bg-custom-blue-700/10 text-custom-blue-700 dark:text-custom-blue-300"
                          : "text-subtle hover:bg-highlight"
                      )}
                    >
                      {d.icon}
                      <span className="truncate">{d.label}</span>
                    </a>
                  );
                })}
              </Col>
            );
          })}
        </nav>

        <div className="min-w-0 flex-1 overflow-auto">
          <div className="p-5">
            {section !== "tokens" && section !== "password" && (
              <SectionHeader title={active.label} description={active.description} />
            )}
            <SectionBody id={section} s={s} go={go} />
          </div>
        </div>
      </div>
    </Content.Card>
  );
}
