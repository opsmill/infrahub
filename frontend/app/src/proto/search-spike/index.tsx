// @ts-nocheck
// Throwaway prototype route for the search anywhere spike. Deleted after the decision.
import { Button } from "@infrahub/ui";
import { SearchIcon } from "lucide-react";
import React from "react";
import { createPortal } from "react-dom";

import Content from "@/shared/components/layout/content";
import Kbd from "@/shared/components/ui/kbd";

import { KINDS, type ProtoNode } from "./data";
import { ResultsPage } from "./results-page";
import { PICKER_CSS, ProtoContext } from "./shared";
import { CurrentVariant } from "./v1-current";
import { OneListVariant } from "./v2-one-list";
import { SectionsPageVariant } from "./v3-sections-page";
import { TopHitVariant } from "./v4-top-hit";

const VARIANTS = [
  { name: "Current", Component: CurrentVariant },
  { name: "One list", Component: OneListVariant },
  { name: "Sections + page", Component: SectionsPageVariant },
  { name: "Top hit", Component: TopHitVariant },
];

const SAMPLES = [
  { q: "atl1-edge1", why: "full device name; today returns 4 interfaces" },
  { q: "atl1", why: "site name, 119 matches" },
  { q: "Ethernet1", why: "48 exact matches" },
  { q: "server", why: "exact on a dropdown value, 342 exact" },
  { q: "atl1_server", why: "one VLAN" },
  { q: "FOC", why: "serial number prefix, no exact" },
  { q: "fra1-frankfurt", why: "long names" },
  { q: "10.1.0.1", why: "IP address, parent prefixes" },
  { q: "zzzz", why: "no match" },
  { q: "fail", why: "server error" },
];

function initialVariant() {
  const v = Number.parseInt(new URLSearchParams(window.location.search).get("v") ?? "", 10);
  return v >= 1 && v <= VARIANTS.length ? v - 1 : 0;
}

function SearchSpikePrototype() {
  const [current, setCurrent] = React.useState(initialVariant);
  const [isOpen, setIsOpen] = React.useState(true);
  const [query, setQuery] = React.useState("atl1-edge1");
  const [caseSensitive, setCaseSensitive] = React.useState(false);
  const [view, setView] = React.useState<"stage" | "results">("stage");
  const [lastOpened, setLastOpened] = React.useState<ProtoNode | null>(null);

  const select = (i: number) => {
    if (i < 0 || i >= VARIANTS.length) return;
    setCurrent(i);
    setView("stage");
    const url = new URL(window.location.href);
    url.searchParams.set("v", String(i + 1));
    window.history.replaceState(null, "", url);
  };

  React.useEffect(() => {
    // Capture phase so the real sidebar search does not also open.
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        e.stopPropagation();
        setIsOpen((o) => !o);
        return;
      }
      const target = e.target as HTMLElement;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const num = Number.parseInt(e.key, 10);
      if (num >= 1 && num <= VARIANTS.length) select(num - 1);
      else if (e.key === "ArrowRight") select((current + 1) % VARIANTS.length);
      else if (e.key === "ArrowLeft") select((current - 1 + VARIANTS.length) % VARIANTS.length);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  });

  const openNode = (node: ProtoNode) => {
    setLastOpened(node);
    setIsOpen(false);
    setView("stage");
  };

  const { Component } = VARIANTS[current];

  return (
    <ProtoContext
      value={{
        isOpen,
        setIsOpen,
        query,
        setQuery,
        caseSensitive,
        setCaseSensitive,
        openNode,
        showResultsPage: () => {
          setIsOpen(false);
          setView("results");
        },
      }}
    >
      <style>{PICKER_CSS}</style>
      {view === "results" ? (
        <ResultsPage />
      ) : (
        <Stage
          lastOpened={lastOpened}
          onOpen={() => setIsOpen(true)}
          onSample={(q) => {
            setQuery(q);
            setIsOpen(true);
          }}
        />
      )}
      <Component key={current} />
      <Picker current={current} onSelect={select} />
    </ProtoContext>
  );
}

function Stage({
  lastOpened,
  onOpen,
  onSample,
}: {
  lastOpened: ProtoNode | null;
  onOpen: () => void;
  onSample: (q: string) => void;
}) {
  return (
    <Content className="p-1">
      <Content.Card className="min-h-full">
        <Content.CardTitle
          title="Search anywhere: exact match and view all"
          description="Prototype with fixture data: 6 sites, 48 devices, 480 interfaces, IP prefixes and addresses."
          end={
            <Button variant="outline" size="sm" onPress={onOpen} className="px-3">
              <SearchIcon />
              Open search
              <Kbd keys="command" className="ml-1 bg-surface">
                K
              </Kbd>
            </Button>
          }
        />
        <div className="space-y-6 p-5">
          {lastOpened && (
            <p className="text-sm">
              <span className="text-subtle">Opened: </span>
              <span className="font-medium">{lastOpened.label}</span>
              <span className="text-subtle">
                {" "}
                · {KINDS[lastOpened.kind].label}
                {lastOpened.context && ` · ${lastOpened.context}`}
              </span>
            </p>
          )}
          <section>
            <h2 className="mb-2 font-medium text-subtle text-xs">Searches to try</h2>
            <div className="flex flex-wrap gap-2">
              {SAMPLES.map((s) => (
                <Button key={s.q} variant="outline" size="xs" onPress={() => onSample(s.q)} className="px-2">
                  <span className="font-medium">{s.q}</span>
                  <span className="text-subtle">{s.why}</span>
                </Button>
              ))}
            </div>
          </section>
        </div>
      </Content.Card>
    </Content>
  );
}

function Picker({ current, onSelect }: { current: number; onSelect: (i: number) => void }) {
  const navRef = React.useRef<HTMLElement>(null);
  const highlightRef = React.useRef<HTMLSpanElement>(null);
  const itemRefs = React.useRef<Array<HTMLButtonElement | null>>([]);

  React.useLayoutEffect(() => {
    const move = () => {
      const el = itemRefs.current[current];
      const hl = highlightRef.current;
      if (!el || !hl) return;
      hl.style.width = `${el.offsetWidth}px`;
      hl.style.transform = `translateX(${el.offsetLeft}px)`;
    };
    move();
    window.addEventListener("resize", move);
    return () => window.removeEventListener("resize", move);
  }, [current]);

  React.useEffect(() => {
    const id = requestAnimationFrame(() =>
      requestAnimationFrame(() => navRef.current?.setAttribute("data-ready", ""))
    );
    return () => cancelAnimationFrame(id);
  }, []);

  return createPortal(
    <nav ref={navRef} className="proto-picker" aria-label="Prototype variants" data-react-aria-top-layer="true">
      <span ref={highlightRef} className="proto-picker-highlight" aria-hidden="true" />
      {VARIANTS.map((v, i) => (
        <button
          key={v.name}
          ref={(el) => {
            itemRefs.current[i] = el;
          }}
          type="button"
          className="proto-picker-item"
          data-active={i === current ? "" : undefined}
          aria-current={i === current ? "true" : undefined}
          onClick={() => onSelect(i)}
        >
          {v.name}
        </button>
      ))}
    </nav>,
    document.body
  );
}

export const Component = SearchSpikePrototype;
