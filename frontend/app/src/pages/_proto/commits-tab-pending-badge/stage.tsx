// PROTOTYPE design-jam commits-tab-pending-badge
import { Card, ScrollArea } from "@infrahub/ui";
import { TriangleAlertIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import {
  BASE_PATH,
  type CommitStateLabel,
  getMeaningLabel,
  type MockCommit,
  pickScenarios,
  pluralizeCommits,
  type Scenario,
} from "./scenarios";

export interface CommitsTabProps {
  scenario: Scenario;
  to: string;
  scrollIntoViewOnActive: boolean;
}

interface StageProps {
  scenarioOption: string;
  renderCommitsTab: (props: CommitsTabProps) => ReactNode;
  insideTop?: (scenario: Scenario) => ReactNode;
  overviewPreview?: (scenario: Scenario) => ReactNode;
  hideCountNotice?: boolean;
}

const TABS = [
  { path: "queries", label: "Queries", count: 0 },
  { path: "transformations", label: "Transformations", count: 0 },
  { path: "checks", label: "Checks", count: 0 },
  { path: "generators", label: "Generators", count: 0 },
  { path: "groups-objects", label: "Groups Objects", count: 0 },
  { path: "tasks", label: "Tasks", count: 3 },
];

const OVERFLOW_TABS = [
  { path: "queries", label: "Queries", count: 12 },
  { path: "transformations", label: "Transformations", count: 48 },
  { path: "artifact-definitions", label: "Artifact Definitions", count: 16 },
  { path: "tasks", label: "Tasks", count: 1024 },
];

const STATE_VARIANT: Record<CommitStateLabel, BadgeProps["variant"]> = {
  "Remote head": "blue",
  Imported: "green",
  "Pending import": "yellow",
  "Not on this branch": "gray",
  "Not on current history": "gray-outline",
};

export function ProtoStage({
  scenarioOption,
  renderCommitsTab,
  insideTop,
  overviewPreview,
  hideCountNotice,
}: StageProps) {
  const location = useLocation();
  const scenarios = pickScenarios(scenarioOption);

  if (location.pathname.replace(/\/$/, "") === BASE_PATH) {
    return <Navigate to={{ pathname: `${BASE_PATH}/commits`, search: location.search }} replace />;
  }

  const [single] = scenarios;
  if (scenarios.length === 1 && single) {
    return (
      <SingleScenario
        scenario={single}
        renderCommitsTab={renderCommitsTab}
        insideTop={insideTop}
        hideCountNotice={hideCountNotice}
      />
    );
  }

  return (
    <Content.Card className="min-h-full">
      <Content.CardTitle
        title="demo-edge"
        description="Every scenario's tab bar at real size. Pick one scenario in the panel to view the inside of the Commits tab."
      />
      <ol className="flex flex-col">
        {scenarios.map((scenario) => (
          <li key={scenario.id} className="flex flex-col gap-1 border-b px-1 pt-3 pb-1">
            <p className="px-4 text-foreground-muted text-xs">
              <span className="font-semibold tabular-nums">{scenario.id}</span> ·{" "}
              {scenario.situation}
            </p>
            <div className={classNames(scenario.overflow && "max-w-225 border-r border-dashed")}>
              <TabBar
                scenario={scenario}
                renderCommitsTab={renderCommitsTab}
                label={`Tabs, scenario ${scenario.id}`}
              />
            </div>
            {overviewPreview && <div className="px-4 pb-2">{overviewPreview(scenario)}</div>}
          </li>
        ))}
      </ol>
    </Content.Card>
  );
}

function TabBar({
  scenario,
  renderCommitsTab,
  label,
  scrollIntoViewOnActive = false,
}: {
  scenario: Scenario;
  renderCommitsTab: StageProps["renderCommitsTab"];
  label: string;
  scrollIntoViewOnActive?: boolean;
}) {
  const tabs = scenario.overflow ? OVERFLOW_TABS : TABS;

  return (
    <ScrollArea scrollX scrollY={false} scrollBarClassName="hidden" className="shrink-0">
      <nav aria-label={label}>
        <Row className="items-end gap-4 px-4">
          <LinkTab to={`${BASE_PATH}/details`}>Details</LinkTab>
          {tabs.map((tab) => (
            <LinkTab key={tab.path} to={`${BASE_PATH}/${tab.path}`}>
              {tab.label}
              <Badge className="rounded-full font-medium text-subtle">{tab.count}</Badge>
            </LinkTab>
          ))}
          <LinkTab to={`${BASE_PATH}/objects`}>Objects</LinkTab>
          {renderCommitsTab({
            scenario,
            to: `${BASE_PATH}/commits`,
            scrollIntoViewOnActive,
          })}
        </Row>
      </nav>
    </ScrollArea>
  );
}

function SingleScenario({
  scenario,
  renderCommitsTab,
  insideTop,
  hideCountNotice,
}: { scenario: Scenario } & Omit<StageProps, "scenarioOption" | "overviewPreview">) {
  const location = useLocation();
  const onCommits = location.pathname.endsWith("/commits");

  return (
    <Content.Card className="h-full">
      <Content.CardTitle
        title="demo-edge"
        description={`Scenario ${scenario.id} · ${scenario.situation}`}
      />
      <Col className={classNames("gap-0 overflow-auto p-1", scenario.overflow && "max-w-225")}>
        <TabBar
          scenario={scenario}
          renderCommitsTab={renderCommitsTab}
          label="Tabs"
          scrollIntoViewOnActive
        />
        <Card variant="panel" className="overflow-auto">
          {onCommits ? (
            <CommitsInside
              scenario={scenario}
              insideTop={insideTop}
              hideCountNotice={hideCountNotice}
            />
          ) : (
            <p className="p-4 text-foreground-muted text-sm">
              This tab is not part of the prototype. Open Commits to view the scenario.
            </p>
          )}
        </Card>
      </Col>
    </Content.Card>
  );
}

function CommitsInside({
  scenario,
  insideTop,
  hideCountNotice,
}: { scenario: Scenario } & Pick<StageProps, "insideTop" | "hideCountNotice">) {
  if (scenario.condition === "LOADING") {
    return <LoadingIndicator className="h-40 p-4" />;
  }

  const toolbar = (
    <Row className="items-center gap-2">
      <RefreshButton className="rounded-md border-border-strong" queryKeys={[["proto-commits"]]} />
      <p className="flex flex-wrap items-center gap-x-1.5 text-foreground-muted text-sm">
        <span className="flex items-center gap-1">
          Tracking <code className="font-mono text-foreground text-xs">main</code>
        </span>
        {scenario.emptyState === null && (
          <span className="flex items-center gap-1">
            Updated <DateDisplay date={Date.now() - 4 * 60_000} fullTimestamp className="text-sm" />
          </span>
        )}
      </p>
    </Row>
  );

  if (scenario.emptyState) {
    return (
      <Col className="gap-0">
        <Col className="p-2">{toolbar}</Col>
        <Col className="items-center gap-1 p-8 text-center">
          <p className="font-medium text-sm">{scenario.emptyState.title}</p>
          <p className="text-foreground-muted text-sm">{scenario.emptyState.message}</p>
        </Col>
      </Col>
    );
  }

  const showCountNotice = !hideCountNotice && scenario.condition === "BEHIND" && scenario.count;

  return (
    <Col className="gap-0">
      {insideTop?.(scenario)}
      <Col className="gap-1.5 p-2">
        {toolbar}
        {scenario.rebaseNote && (
          <p className="text-foreground-muted text-sm">{scenario.rebaseNote}</p>
        )}
        {scenario.warning && (
          <Row
            role="note"
            className="rounded-md border border-warning-border bg-warning-surface px-3 py-2 text-sm text-warning"
          >
            <TriangleAlertIcon className="size-4 shrink-0" aria-hidden="true" />
            <p>{scenario.warning}</p>
          </Row>
        )}
        {showCountNotice && (
          <p className="font-medium text-sm">
            {pluralizeCommits(scenario.count ?? 0)} {getMeaningLabel(scenario.meaning)}
          </p>
        )}
      </Col>
      <CommitTable commits={scenario.commits} />
    </Col>
  );
}

function CommitTable({ commits }: { commits: MockCommit[] }) {
  return (
    <table className="w-full border-t text-sm">
      <thead>
        <tr className="text-left text-foreground-muted text-xs">
          <th className="px-3 py-2 font-medium">Commit</th>
          <th className="px-3 py-2 font-medium">Message</th>
          <th className="px-3 py-2 font-medium">Author</th>
          <th className="px-3 py-2 font-medium">Date</th>
          <th className="px-3 py-2 font-medium">State</th>
        </tr>
      </thead>
      <tbody>
        {commits.map((commit) => (
          <tr key={commit.hash} className="border-t">
            <td className="px-3 py-2 font-mono text-xs">{commit.hash}</td>
            <td className="max-w-md truncate px-3 py-2">{commit.message}</td>
            <td className="whitespace-nowrap px-3 py-2">{commit.author}</td>
            <td className="px-3 py-2">
              <DateDisplay date={Date.now() - commit.minutesAgo * 60_000} />
            </td>
            <td className="px-3 py-2">
              <Row className="flex-wrap gap-1">
                {commit.states.map((state) => (
                  <Badge key={state} variant={STATE_VARIANT[state]}>
                    {state}
                  </Badge>
                ))}
              </Row>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
