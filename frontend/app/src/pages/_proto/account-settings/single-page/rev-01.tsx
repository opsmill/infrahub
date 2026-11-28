// PROTOTYPE design-jam account-settings — direction "single-page", rev 1. Frozen.
// Every section on one scrolling page; an "on this page" rail tracks and jumps.

import { useEffect, useRef, useState } from "react";

import { Col } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { classNames } from "@/shared/utils/common";

import type { KnobValue } from "../design-history-panel";
import {
  IdentityHeader,
  resolveSection,
  SectionBody,
  SectionHeader,
  type SectionId,
  sectionsFor,
  toScenario,
  useSection,
} from "../sections-v1";

export function SinglePageRev01({ knobs }: { knobs: Record<string, KnobValue> }) {
  const s = toScenario(knobs);
  const defs = sectionsFor(s);
  const [asked, go] = useSection("profile");
  const target = resolveSection(asked, defs);
  const scroller = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState<SectionId>(target);

  const jump = (id: SectionId, smooth = true) => {
    const el = scroller.current?.querySelector(`#settings-${id}`);
    el?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  };

  // Deep link: land on the asked section once the page has rendered.
  useEffect(() => {
    requestAnimationFrame(() => jump(target, false));
  }, []);

  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const io = new IntersectionObserver(
      (entries) => {
        const top = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (top) setInView(top.target.id.replace("settings-", "") as SectionId);
      },
      { root, rootMargin: "0px 0px -60% 0px" }
    );
    for (const el of root.querySelectorAll("[data-settings-section]")) io.observe(el);
    return () => io.disconnect();
  });

  return (
    <Content.Card className="flex h-full flex-col">
      <Content.CardTitle title="Account settings" />

      <div ref={scroller} className="min-h-0 flex-1 overflow-auto">
        <div className="mx-auto flex max-w-6xl gap-8 p-5">
          <Col className="min-w-0 flex-1 gap-10">
            <IdentityHeader s={s} />
            {defs.map((d) => (
              <section
                key={d.id}
                id={`settings-${d.id}`}
                data-settings-section
                aria-labelledby={`settings-${d.id}-title`}
                className="scroll-mt-5"
              >
                {(d.id !== "tokens" && d.id !== "password") || !s.p2 ? (
                  <SectionHeader title={d.label} description={d.description} />
                ) : null}
                <span id={`settings-${d.id}-title`} hidden>
                  {d.label}
                </span>
                <SectionBody
                  id={d.id}
                  s={s}
                  go={(id) => {
                    go(id);
                    jump(id);
                  }}
                />
              </section>
            ))}
          </Col>

          <nav
            aria-label="On this page"
            className="sticky top-0 hidden w-48 shrink-0 self-start lg:block"
          >
            <div className="pb-2 font-medium text-foreground-muted text-xs">On this page</div>
            <Col className="gap-0.5 border-l">
              {defs.map((d) => (
                <a
                  key={d.id}
                  href={`?section=${d.id}`}
                  aria-current={inView === d.id ? "location" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    go(d.id);
                    jump(d.id);
                  }}
                  className={classNames(
                    "-ml-px border-l-2 py-1 pl-3 text-sm outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo",
                    inView === d.id
                      ? "border-custom-blue-600 font-medium text-foreground"
                      : "border-transparent text-foreground-muted hover:text-foreground"
                  )}
                >
                  {d.label}
                </a>
              ))}
            </Col>
          </nav>
        </div>
      </div>
    </Content.Card>
  );
}
