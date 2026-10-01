// PROTOTYPE design-jam account-settings — direction "overview", rev 2. Frozen.
// A landing grid of section cards with a live summary each; a card opens its section.

import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";

import { useTheme } from "@/entities/config/ui/theme-provider";

import type { KnobValue } from "../design-history-panel";
import {
  IdentityHeader,
  resolveSection,
  SectionBody,
  type SectionDef,
  SectionHeader,
  sectionSummary,
  sectionsFor,
  toScenario,
  useSection,
} from "../sections-v2";

const THEME_LABEL = { system: "System", light: "Light", dark: "Dark" } as const;

export function OverviewRev02({ knobs }: { knobs: Record<string, KnobValue> }) {
  const s = toScenario(knobs);
  const defs = sectionsFor(s);
  const [asked, go] = useSection(null);
  const { theme } = useTheme();

  if (asked) {
    const section = resolveSection(asked, defs);
    const active = defs.find((d) => d.id === section) as SectionDef;
    return (
      <Content.Card className="flex h-full flex-col">
        <Content.CardTitle
          title={
            <Row className="min-w-0 items-center gap-1">
              <a
                href="?"
                onClick={(e) => {
                  e.preventDefault();
                  go(null);
                }}
                className="flex items-center gap-0.5 rounded-md font-normal text-foreground-muted outline-hidden hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring-halo"
              >
                <ChevronLeftIcon className="size-5" />
                Account settings
              </a>
              <span className="text-foreground-muted">/</span>
              <span className="truncate">{active.label}</span>
            </Row>
          }
        />
        <div className="min-h-0 flex-1 overflow-auto p-5">
          {(section !== "tokens" && section !== "password") || !s.p2 ? (
            <SectionHeader title={active.label} description={active.description} />
          ) : null}
          <SectionBody id={section} s={s} go={go} />
        </div>
      </Content.Card>
    );
  }

  const groups = ["Personal", "Administration"] as const;

  return (
    <Content.Card className="flex h-full flex-col">
      <Content.CardTitle title="Account settings" />
      <div className="min-h-0 flex-1 overflow-auto p-5">
        <Col className="mx-auto max-w-5xl gap-8">
          <IdentityHeader s={s} />
          {groups.map((g) => {
            const items = defs.filter((d) => d.group === g);
            if (items.length === 0) return null;
            return (
              <Col key={g} className="gap-3">
                <h2 className="font-medium text-foreground-muted text-sm">{g}</h2>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {items.map((d) => (
                    <a
                      key={d.id}
                      href={`?section=${d.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        go(d.id);
                      }}
                      className="group flex items-start gap-3 rounded-2xl border bg-card p-4 shadow-card outline-hidden transition-colors hover:border-border-strong focus-visible:ring-2 focus-visible:ring-ring-halo"
                    >
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-content-strong text-foreground-muted">
                        {d.icon}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold">{d.label}</div>
                        <p className="text-foreground-muted text-sm">{d.description}</p>
                        {sectionSummary(d.id, s, THEME_LABEL[theme]) && (
                          <p className="mt-2 font-medium text-sm">
                            {sectionSummary(d.id, s, THEME_LABEL[theme])}
                          </p>
                        )}
                      </div>
                      <ChevronRightIcon className="mt-1 size-4 shrink-0 text-foreground-muted transition-transform group-hover:translate-x-0.5" />
                    </a>
                  ))}
                </div>
              </Col>
            );
          })}
        </Col>
      </div>
    </Content.Card>
  );
}
