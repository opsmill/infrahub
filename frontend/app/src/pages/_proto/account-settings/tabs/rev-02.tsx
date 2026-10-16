// PROTOTYPE design-jam account-settings — direction "tabs", rev 2. Frozen.
// Today's structure kept: identity header, horizontal tabs. What changes is which tabs
// exist (Preferences, Global preferences) and what each one holds.

import { Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { classNames } from "@/shared/utils/common";

import type { KnobValue } from "../design-history-panel";
import {
  IdentityHeader,
  resolveSection,
  SectionBody,
  sectionsFor,
  toScenario,
  useSection,
} from "../sections-v2";

export function TabsRev02({ knobs }: { knobs: Record<string, KnobValue> }) {
  const s = toScenario(knobs);
  const defs = sectionsFor(s);
  const [asked, go] = useSection("profile");
  const section = resolveSection(asked, defs);

  return (
    <Content.Card className="flex h-full flex-col">
      <Content.CardTitle title={<IdentityHeader s={s} />} />

      <nav aria-label="Tabs">
        <Row className="overflow-x-auto border-b">
          {defs.map((d) => {
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
                  "transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo",
                  "inline-flex h-11 items-center gap-2 truncate border-transparent border-b-2 px-3 py-2 font-medium text-sm",
                  isActive
                    ? "border-custom-blue-600 text-custom-blue-600"
                    : "text-foreground-muted hover:border-border-strong hover:text-foreground",
                  d.group === "Administration" && "ml-auto"
                )}
              >
                {s.p2 && d.icon}
                {d.label}
              </a>
            );
          })}
        </Row>
      </nav>

      <div className={classNames("min-h-0 flex-1 overflow-auto", s.p2 && "p-5")}>
        <SectionBody id={section} s={s} go={go} />
      </div>
    </Content.Card>
  );
}
