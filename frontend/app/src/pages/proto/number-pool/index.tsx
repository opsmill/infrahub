// PROTO number-pool — harness for /proto/number-pool. Delete with the prototype.
import "./picker.css";

import React from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router";

import Content from "@/shared/components/layout/content";

import { CreatePoolSheet } from "./create-form";
import { DATASETS, type Dataset } from "./data";
import { EditPoolContext, EditPoolSheet } from "./editor";
import { PoolDetails } from "./page";

type View = "details" | "create" | "edit";

function PoolPage({ dataset, view }: { dataset: Dataset; view: View }) {
  const [isEditOpen, setIsEditOpen] = React.useState(
    view === "edit" && !dataset.pool.schemaDefined
  );
  const [isCreateOpen, setIsCreateOpen] = React.useState(view === "create");
  return (
    <EditPoolContext value={() => setIsEditOpen(true)}>
      <PoolDetails dataset={dataset} />
      <EditPoolSheet dataset={dataset} isOpen={isEditOpen} onOpenChange={setIsEditOpen} />
      <CreatePoolSheet isOpen={isCreateOpen} onOpenChange={setIsCreateOpen} />
    </EditPoolContext>
  );
}

const withView =
  (view: View) =>
  ({ dataset }: { dataset: Dataset }) => <PoolPage dataset={dataset} view={view} />;

const VARIANTS = [
  { name: "Details", render: withView("details") },
  { name: "Create", render: withView("create") },
  { name: "Edit", render: withView("edit") },
];

function Pill({
  label,
  items,
  current,
  onSelect,
  style,
}: {
  label: string;
  items: string[];
  current: number;
  onSelect: (i: number) => void;
  style?: React.CSSProperties;
}) {
  const navRef = React.useRef<HTMLElement>(null);
  const highlightRef = React.useRef<HTMLSpanElement>(null);
  const itemRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  React.useLayoutEffect(() => {
    const move = () => {
      const el = itemRefs.current[current];
      const highlight = highlightRef.current;
      if (!el || !highlight) return;
      highlight.style.width = `${el.offsetWidth}px`;
      highlight.style.transform = `translateX(${el.offsetLeft}px)`;
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

  // a modal sheet marks everything outside it inert; the top-layer flag and a body portal keep the picker usable
  return createPortal(
    <nav
      ref={navRef}
      className="proto-picker"
      aria-label={label}
      style={style}
      data-react-aria-top-layer="true"
    >
      <span ref={highlightRef} className="proto-picker-highlight" aria-hidden="true" />
      {items.map((item, i) => (
        <button
          key={item}
          type="button"
          ref={(el) => {
            itemRefs.current[i] = el;
          }}
          className="proto-picker-item"
          data-active={i === current ? "" : undefined}
          aria-current={i === current ? "true" : undefined}
          onClick={() => onSelect(i)}
        >
          {item}
        </button>
      ))}
    </nav>,
    document.body
  );
}

function NumberPoolProto() {
  const [params, setParams] = useSearchParams();
  const variantIndex = Math.min(
    VARIANTS.length - 1,
    Math.max(0, (Number(params.get("v")) || 1) - 1)
  );
  const datasetIndex = Math.max(
    0,
    DATASETS.findIndex((d) => d.key === params.get("d"))
  );
  const dataset = DATASETS[datasetIndex]!;

  const setParam = (key: string, value: string) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set(key, value);
        return next;
      },
      { replace: true }
    );
  };
  const setVariant = (i: number) => setParam("v", String(i + 1));

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const num = Number.parseInt(e.key, 10);
      if (num >= 1 && num <= VARIANTS.length) setVariant(num - 1);
      else if (e.key === "ArrowRight") setVariant((variantIndex + 1) % VARIANTS.length);
      else if (e.key === "ArrowLeft")
        setVariant((variantIndex - 1 + VARIANTS.length) % VARIANTS.length);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const variant = VARIANTS[variantIndex]!;
  const Variant = variant.render;

  return (
    <>
      <Content.Card className="grow">
        <Variant key={`${variantIndex}-${dataset.key}`} dataset={dataset} />
      </Content.Card>
      <Pill
        label="Prototype dataset"
        items={DATASETS.map((d) => d.label)}
        current={datasetIndex}
        onSelect={(i) =>
          setParams(
            (prev) => {
              const next = new URLSearchParams(prev);
              next.set("d", DATASETS[i]!.key);
              next.delete("scope");
              return next;
            },
            { replace: true }
          )
        }
        style={{ bottom: 64 }}
      />
      <Pill
        label="Prototype variants"
        items={VARIANTS.map((v) => v.name)}
        current={variantIndex}
        onSelect={setVariant}
      />
    </>
  );
}

export const Component = NumberPoolProto;
