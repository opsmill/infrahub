// PROTOTYPE — one frozen revision of the branch details page. Page chrome + the three directions.
// Frozen: never import from another revision's folder; copy the folder to make the next revision.
import "./controls.css";

import { Card } from "@infrahub/ui";
import { useState } from "react";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Col, Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { classNames } from "@/shared/utils/common";

import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";

import { BranchActionsMenu } from "./branch-actions-menu";
import { buildData, type Scenario } from "./data";
import type { LocateTarget } from "./locate";
import type { OnLocate } from "./merge-rail";
import type { VariantProps } from "./shared";
import { ConsistentVariant } from "./v-consistent";
import { LegacyVariant } from "./v-legacy";
import { ObjectVariant } from "./v-object";

export type RevKnobs = {
  scenario: Scenario;
  repos: number;
  bands: number;
  rail: number;
};

const COMPONENTS = {
  consistent: ConsistentVariant,
  legacy: LegacyVariant,
  object: ObjectVariant,
} as const;
export type VariantId = keyof typeof COMPONENTS;

const TABS = ["Details", "Data", "Files", "Artifacts", "Schema"] as const;

function TabRow({
  tab,
  setTab,
  className,
}: {
  tab: string;
  setTab: (t: string) => void;
  className: string;
}) {
  return (
    <nav aria-label="Tabs">
      <Row className={className}>
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            aria-current={t === tab ? "page" : undefined}
            className={classNames(
              "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25",
              "inline-flex h-11 items-center gap-2 border-b-2 px-3 py-2 font-medium text-sm transition-colors",
              t === tab
                ? "border-custom-blue-600 text-custom-blue-600"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            )}
          >
            {t}
          </button>
        ))}
      </Row>
    </nav>
  );
}

export function RevRoot({ variant, knobs }: { variant: VariantId; knobs: RevKnobs }) {
  const [tab, setTab] = useState<string>("Details");
  const [locate, setLocate] = useState<LocateTarget | null>(null);
  const [refreshedAt, setRefreshedAt] = useState(() => new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [reposPage, setReposPage] = useState(1);
  const [tasksPage, setTasksPage] = useState(1);

  const refresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
      setRefreshedAt(new Date());
    }, 700);
  };

  const onLocate: OnLocate = (target) => {
    setTab("Details");
    setLocate({ ...target, nonce: Date.now() });
  };

  const data = buildData(knobs.scenario, knobs.repos);
  const props: VariantProps = {
    data,
    locate,
    onLocate,
    railWidth: knobs.rail,
    tasksPage,
    onTasksPage: setTasksPage,
    card: {
      page: reposPage,
      onPageChange: setReposPage,
      maxBands: knobs.bands,
      refreshedAt,
      isRefreshing,
      onRefresh: refresh,
    },
  };
  const Component = COMPONENTS[variant];
  const body =
    tab === "Details" ? (
      <Component {...props} />
    ) : (
      <div className="flex h-60 items-center justify-center text-neutral-500 text-sm">
        {tab} is unchanged by this redesign.
      </div>
    );

  return (
    <Content.Card>
      <div className="flex items-center gap-2 border-custom-blue-700/15 border-b bg-custom-blue-700/5 px-5 py-2 text-custom-blue-700 text-sm">
        You're working on this branch.
      </div>

      {variant === "object" ? (
        <>
          <Row className="w-full p-2 pb-1.5 pl-3">
            <h1 className="truncate font-bold text-xl" title={data.branch.name}>
              {data.branch.name}
            </h1>
            <CopyToClipboardButton data={data.branch.name} />
            <RefreshButton
              className="ml-auto"
              queryKey={["proto-branch-details"]}
              onPress={refresh}
            />
            <BranchActionsMenu branchName={data.branch.name} />
          </Row>
          <Col className="gap-0 p-1">
            <TabRow tab={tab} setTab={setTab} className="items-end gap-4 px-4" />
            <Card className="to-neutral-50">{body}</Card>
          </Col>
        </>
      ) : (
        <>
          <header className="flex items-start justify-between gap-4 p-5 pb-2">
            <div className="min-w-0">
              <h1 className="truncate font-bold text-xl" title={data.branch.name}>
                {data.branch.name}
              </h1>
              <p className="max-w-prose text-pretty text-sm">{data.branch.description}</p>
            </div>
            {variant === "consistent" && <BranchActionsMenu branchName={data.branch.name} />}
          </header>
          <TabRow tab={tab} setTab={setTab} className="border-gray-200 border-b" />
          {body}
        </>
      )}
    </Content.Card>
  );
}
