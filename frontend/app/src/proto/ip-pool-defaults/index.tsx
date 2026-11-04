import React from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router";

import { DATASETS, type ProtoPool } from "./data";
import { ChainedVariant } from "./s-chained";
import { DividerVariant } from "./s-divider";
import { DotsVariant } from "./s-dots";
import { NoWrapVariant } from "./s-nowrap";

const VARIANTS: { name: string; Component: React.ComponentType<{ pool: ProtoPool }> }[] = [
  { name: "Dots", Component: DotsVariant },
  { name: "Divider", Component: DividerVariant },
  { name: "Chained", Component: ChainedVariant },
  { name: "No wrap", Component: NoWrapVariant },
];

const PICKER_CSS = `
.proto-picker { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); z-index: 2147483647; display: flex; align-items: center; gap: 2px; padding: 4px; border-radius: 999px; background: rgba(10, 10, 10, 0.82); -webkit-backdrop-filter: blur(12px) saturate(1.4); backdrop-filter: blur(12px) saturate(1.4); box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08) inset, 0 8px 24px rgba(0, 0, 0, 0.24), 0 2px 6px rgba(0, 0, 0, 0.12); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 13px; line-height: 1; -webkit-font-smoothing: antialiased; user-select: none; -webkit-user-select: none; }
.proto-picker-highlight { position: absolute; top: 4px; left: 0; height: 28px; border-radius: 999px; background: rgba(255, 255, 255, 0.12); will-change: transform; }
.proto-picker[data-ready] .proto-picker-highlight { transition: transform 250ms cubic-bezier(0.23, 1, 0.32, 1), width 250ms cubic-bezier(0.23, 1, 0.32, 1); }
@media (prefers-reduced-motion: reduce) { .proto-picker[data-ready] .proto-picker-highlight { transition: none; } }
.proto-picker-item { position: relative; display: flex; align-items: center; height: 28px; padding: 0 12px; border: 0; border-radius: 999px; background: transparent; color: rgba(255, 255, 255, 0.55); font: inherit; cursor: pointer; transition: color 150ms ease-out; }
.proto-picker-item:hover { color: rgba(255, 255, 255, 0.85); }
.proto-picker-item:active { transform: scale(0.97); }
.proto-picker-item:focus-visible { outline: 2px solid rgba(255, 255, 255, 0.4); outline-offset: 2px; }
.proto-picker-item[data-active] { color: #fff; }
.proto-picker[data-position="top"] { bottom: auto; top: 24px; }
`;

interface PillProps {
  label: string;
  items: string[];
  active: number;
  onSelect: (index: number) => void;
  position?: "top";
}

function Pill({ label, items, active, onSelect, position }: PillProps) {
  const itemRefs = React.useRef<(HTMLButtonElement | null)[]>([]);
  const highlightRef = React.useRef<HTMLSpanElement>(null);
  const [isReady, setIsReady] = React.useState(false);

  React.useLayoutEffect(() => {
    const moveHighlight = () => {
      const item = itemRefs.current[active];
      const highlight = highlightRef.current;
      if (!item || !highlight) return;
      highlight.style.width = `${item.offsetWidth}px`;
      highlight.style.transform = `translateX(${item.offsetLeft}px)`;
    };
    moveHighlight();
    window.addEventListener("resize", moveHighlight);
    return () => window.removeEventListener("resize", moveHighlight);
  }, [active]);

  React.useEffect(() => {
    const frame = requestAnimationFrame(() => requestAnimationFrame(() => setIsReady(true)));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <nav
      className="proto-picker"
      aria-label={label}
      data-ready={isReady ? "" : undefined}
      data-position={position}
      data-react-aria-top-layer="true"
    >
      <span ref={highlightRef} className="proto-picker-highlight" aria-hidden="true" />
      {items.map((item, index) => (
        <button
          key={item}
          ref={(element) => {
            itemRefs.current[index] = element;
          }}
          type="button"
          className="proto-picker-item"
          data-active={index === active ? "" : undefined}
          aria-current={index === active ? "true" : undefined}
          onClick={() => onSelect(index)}
        >
          {item}
        </button>
      ))}
    </nav>
  );
}

const readIndex = (value: string | null, length: number) => {
  const index = Number.parseInt(value ?? "1", 10) - 1;
  return index >= 0 && index < length ? index : 0;
};

function IpPoolDefaultsProto() {
  const [searchParams, setSearchParams] = useSearchParams();
  const variantIndex = readIndex(searchParams.get("v"), VARIANTS.length);
  const datasetIndex = readIndex(searchParams.get("data"), DATASETS.length);

  const setParam = (name: string, index: number) =>
    setSearchParams(
      (params) => {
        params.set(name, String(index + 1));
        return params;
      },
      { replace: true }
    );

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || target.isContentEditable) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const number = Number.parseInt(event.key, 10);
      if (number >= 1 && number <= VARIANTS.length) setParam("v", number - 1);
      else if (event.key === "ArrowRight") setParam("v", (variantIndex + 1) % VARIANTS.length);
      else if (event.key === "ArrowLeft")
        setParam("v", (variantIndex - 1 + VARIANTS.length) % VARIANTS.length);
      else if (event.key === "d" || event.key === "D")
        setParam("data", (datasetIndex + 1) % DATASETS.length);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  });

  const { Component, name } = VARIANTS[variantIndex]!;
  const { pool } = DATASETS[datasetIndex]!;

  return (
    <>
      <style>{PICKER_CSS}</style>
      <Component key={`${name}-${pool.id}`} pool={pool} />
      {createPortal(
        <>
          <Pill
            label="Prototype data"
            items={DATASETS.map(({ label }) => label)}
            active={datasetIndex}
            onSelect={(index) => setParam("data", index)}
            position="top"
          />
          <Pill
            label="Prototype variants"
            items={VARIANTS.map((variant) => variant.name)}
            active={variantIndex}
            onSelect={(index) => setParam("v", index)}
          />
        </>,
        document.body
      )}
    </>
  );
}

export const Component = IpPoolDefaultsProto;
