// @ts-nocheck
// Throwaway prototype harness. Deleted after the decision.
import { Button, ModalOverlay, Tooltip } from "@infrahub/ui";
import { Command } from "cmdk";
import { CaseSensitiveIcon } from "lucide-react";
import React from "react";
import { Dialog, Modal } from "react-aria-components";

import { Icon } from "@/shared/components/display/icon";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { CommandItem } from "@/shared/components/ui/command";
import { inputStyle } from "@/shared/components/ui/style";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { classNames } from "@/shared/utils/common";

import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";

import { KINDS, type ProtoNode, searchDocs, searchGoTo } from "./data";

// ---------- harness context ----------

export type ProtoCtx = {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  query: string;
  setQuery: (q: string) => void;
  caseSensitive: boolean;
  setCaseSensitive: (cs: boolean) => void;
  openNode: (node: ProtoNode) => void;
  showResultsPage: () => void;
};

export const ProtoContext = React.createContext<ProtoCtx | null>(null);
export const useProto = () => React.use(ProtoContext)!;

// ---------- fake network ----------

export type FakeState<T> = {
  status: "idle" | "loading" | "error" | "success";
  data: T | undefined;
  retry: () => void;
};

/** Debounced fake request; a query containing "fail" errors so the error state can be judged. */
export function useFakeSearch<T>(
  q: string,
  run: (q: string) => T,
  { key = "", enabled = true, delay = [320, 600] }: { key?: string; enabled?: boolean; delay?: [number, number] } = {}
): FakeState<T> {
  const debounced = useDebounce(q.trim(), 300);
  const runRef = React.useRef(run);
  runRef.current = run;
  const [attempt, setAttempt] = React.useState(0);
  const [state, setState] = React.useState<{ status: FakeState<T>["status"]; data?: T }>({ status: "idle" });

  React.useEffect(() => {
    if (!debounced || !enabled) {
      setState({ status: "idle" });
      return;
    }
    let cancelled = false;
    setState({ status: "loading" });
    const t = setTimeout(
      () => {
        if (cancelled) return;
        if (debounced.toLowerCase().includes("fail")) setState({ status: "error" });
        else setState({ status: "success", data: runRef.current(debounced) });
      },
      delay[0] + Math.random() * (delay[1] - delay[0])
    );
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [debounced, key, enabled, attempt]);

  const typing = q.trim() !== debounced;
  const status = !enabled || q.trim() === "" ? "idle" : typing ? "loading" : state.status;
  return { status, data: status === "success" ? state.data : undefined, retry: () => setAttempt((a) => a + 1) };
}

// ---------- dialog chrome, identical to production ----------

export function SearchDialogShell({ children }: { children: React.ReactNode }) {
  const { isOpen, setIsOpen } = useProto();
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={setIsOpen}>
      <Modal
        className={classNames(
          "fixed top-1 left-1/2 z-50 w-full max-w-(--breakpoint-md) -translate-x-1/2 rounded-2xl p-1",
          "border border-modal-frame-border bg-modal-frame shadow-modal backdrop-blur-lg",
          "data-entering:zoom-in-95 data-entering:slide-in-from-top-1/2 data-entering:animate-in data-entering:duration-200",
          "data-exiting:zoom-out-95 data-exiting:slide-out-to-top-1/2 data-exiting:animate-out data-exiting:duration-150"
        )}
      >
        <Dialog
          aria-label="Search anywhere"
          className="no-scrollbar max-h-[calc(var(--visual-viewport-height)*0.95)] overflow-auto rounded-xl bg-background p-2 outline-hidden"
        >
          {children}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

export function SearchInput(props: React.ComponentProps<typeof Command.Input>) {
  const { query, setQuery, caseSensitive, setCaseSensitive } = useProto();
  return (
    <div className="relative">
      <div className="absolute top-2.5 pl-2.5">
        <Icon icon="mdi:magnify" className="text-accent text-xl" />
      </div>
      <Command.Input
        autoFocus
        value={query}
        onValueChange={setQuery}
        placeholder="Search for objects, attributes, schemas, documentations ..."
        className={classNames(inputStyle, "pr-10 pl-9")}
        {...props}
      />
      <Tooltip message="Case sensitive">
        <Button
          variant={caseSensitive ? "primary" : "ghost"}
          size="xs"
          shape="circle"
          aria-label="Case sensitive"
          onPress={() => setCaseSensitive(!caseSensitive)}
          className={classNames("absolute top-1 right-1 size-8 rounded", !caseSensitive && "text-subtle-muted")}
        >
          <CaseSensitiveIcon className="size-5" />
        </Button>
      </Tooltip>
    </div>
  );
}

// ---------- unchanged groups around the objects ----------

export function GoToGroup() {
  const { query } = useProto();
  const goTo = searchGoTo(query);
  if (!query.trim() || goTo.length === 0) return null;
  return (
    <SearchAnywhereGroup heading="Go to">
      {goTo.map((g) => (
        <CommandItem key={g.path} value={g.path}>
          <span className="font-medium">{g.section}</span>
          <Icon icon="mdi:chevron-right" />
          <span className="font-semibold">{g.label}</span>
        </CommandItem>
      ))}
    </SearchAnywhereGroup>
  );
}

export function DocsGroup() {
  const { query } = useProto();
  const docs = useFakeSearch(query, searchDocs);
  if (docs.status === "loading") {
    return (
      <SearchAnywhereGroup heading="Documentation">
        <CommandItem disabled value="loading-docs">
          Loading...
        </CommandItem>
      </SearchAnywhereGroup>
    );
  }
  if (docs.status !== "success" || docs.data.length === 0) return null;
  return (
    <SearchAnywhereGroup heading="Documentation">
      {docs.data.map((doc) => (
        <CommandItem key={doc.title} value={doc.title} className="flex-col items-start gap-0">
          <div className="font-medium text-sm">{doc.title}</div>
          <div className="truncate text-foreground-muted text-xs">{doc.breadcrumb.join(" > ")}</div>
        </CommandItem>
      ))}
    </SearchAnywhereGroup>
  );
}

export function ParentPrefixesGroup({ prefixes }: { prefixes: ProtoNode[] | undefined }) {
  if (!prefixes || prefixes.length === 0) return null;
  return (
    <SearchAnywhereGroup heading="Parent Prefixes">
      {prefixes.map((node) => (
        <NodeRow key={node.id} node={node} />
      ))}
    </SearchAnywhereGroup>
  );
}

export function LoadingObjects({ heading = "Objects" }: { heading?: string }) {
  return (
    <SearchAnywhereGroup heading={heading}>
      <CommandItem disabled value={`loading-${heading}`}>
        Loading...
      </CommandItem>
    </SearchAnywhereGroup>
  );
}

// ---------- the production result row, unchanged ----------

/** Fakes the per-row detail request the real row makes; rows the user cannot view fail and vanish. */
export function useRowDetails(node: ProtoNode) {
  const [state, setState] = React.useState<"loading" | "error" | "ok">("loading");
  React.useEffect(() => {
    const t = setTimeout(() => setState(node.kind === "CoreAccount" ? "error" : "ok"), 200 + Math.random() * 600);
    return () => clearTimeout(t);
  }, [node]);
  return state;
}

export function RowSkeleton() {
  return (
    <Command.Item disabled className="flex w-full py-2">
      <Skeleton className="mx-1 mr-2 h-6 w-6 rounded-sm" />
      <div className="grow space-y-2">
        <div className="flex space-x-2">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-3 w-20" />
        </div>
        <div className="space-y-1">
          <Skeleton className="h-3 max-w-xl" />
          <Skeleton className="h-3 max-w-xl" />
        </div>
      </div>
    </Command.Item>
  );
}

export function ExactMatchBadge() {
  return (
    <Badge variant="green" className="py-0 text-xxs">
      Exact match
    </Badge>
  );
}

export function nodeColumns(node: ProtoNode) {
  return [
    ...node.fields.filter((fl) => !["name", "hfid", "password"].includes(fl.name) && fl.value !== node.label),
    ...node.peers,
  ].slice(0, node.ipNamespace ? 6 : 7);
}

export function NodeRow({ node, exact = false }: { node: ProtoNode; exact?: boolean }) {
  const { openNode } = useProto();
  const state = useRowDetails(node);

  if (state === "error") return null;
  if (state === "loading") return <RowSkeleton />;

  const meta = KINDS[node.kind];

  return (
    <CommandItem value={node.id} onSelect={() => openNode(node)}>
      <Icon icon={meta.icon} className="px-2 py-0.5 text-accent text-lg" />
      <div className="grow overflow-auto text-sm">
        <div className="flex justify-between">
          <span className="mr-1 inline-flex items-center gap-2">
            <span className="font-semibold text-accent">{node.label}</span>
            {exact && <ExactMatchBadge />}
          </span>
          <div className="inline-flex shrink-0 items-center gap-1">
            <Badge variant="blue" className="py-0 text-xxs">
              {meta.namespace}
            </Badge>
            <span className="mr-2 font-medium text-xxs">{meta.label}</span>
          </div>
        </div>
        <div className="mt-1 flex gap-5 text-foreground-muted">
          {nodeColumns(node).map((col) => (
            <div key={col.name} className="flex flex-col overflow-hidden whitespace-nowrap text-xxs leading-3">
              <span>{col.label}</span>
              <span className="truncate font-medium text-foreground">{col.value || "-"}</span>
            </div>
          ))}
        </div>
      </div>
    </CommandItem>
  );
}

// ---------- picker (PICKER.md, verbatim) ----------

export const PICKER_CSS = `
.proto-picker{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:2147483647;display:flex;align-items:center;gap:2px;padding:4px;border-radius:999px;background:rgba(10,10,10,0.82);-webkit-backdrop-filter:blur(12px) saturate(1.4);backdrop-filter:blur(12px) saturate(1.4);box-shadow:0 0 0 1px rgba(255,255,255,0.08) inset,0 8px 24px rgba(0,0,0,0.24),0 2px 6px rgba(0,0,0,0.12);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;line-height:1;-webkit-font-smoothing:antialiased;user-select:none;-webkit-user-select:none}
.proto-picker-highlight{position:absolute;top:4px;left:0;height:28px;border-radius:999px;background:rgba(255,255,255,0.12);will-change:transform}
.proto-picker[data-ready] .proto-picker-highlight{transition:transform 250ms cubic-bezier(0.23,1,0.32,1),width 250ms cubic-bezier(0.23,1,0.32,1)}
@media (prefers-reduced-motion: reduce){.proto-picker[data-ready] .proto-picker-highlight{transition:none}}
.proto-picker-item{position:relative;display:flex;align-items:center;height:28px;padding:0 12px;border:0;border-radius:999px;background:transparent;color:rgba(255,255,255,0.55);font:inherit;cursor:pointer;transition:color 150ms ease-out}
.proto-picker-item:hover{color:rgba(255,255,255,0.85)}
.proto-picker-item:active{transform:scale(0.97)}
.proto-picker-item:focus-visible{outline:2px solid rgba(255,255,255,0.4);outline-offset:2px}
.proto-picker-item[data-active]{color:#fff}
.proto-picker-divider{width:1px;height:16px;margin:0 4px;background:rgba(255,255,255,0.12)}
.proto-picker-replay{padding:0 10px;font-size:14px}
.proto-picker[data-position="top"]{bottom:auto;top:24px}
`;
