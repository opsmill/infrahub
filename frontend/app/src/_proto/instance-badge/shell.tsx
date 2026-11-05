// PROTOTYPE design-jam instance-badge
import {
  Breadcrumb,
  Breadcrumbs,
  Button,
  Card,
  CardContent,
  CardHeader,
  Label,
  ScrollArea,
} from "@infrahub/ui";
import { ChevronsUpDownIcon, EllipsisVerticalIcon, PanelLeftCloseIcon } from "lucide-react";
import { type ReactNode, useEffect } from "react";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { Separator } from "@/shared/components/aria/separator";
import { Col, Row } from "@/shared/components/container";
import { Avatar } from "@/shared/components/display/avatar";
import { Icon } from "@/shared/components/display/icon";
import { SidebarContent, SidebarFooter, SidebarHeader } from "@/shared/components/layout/sidebar";
import { Badge } from "@/shared/components/ui/badge";
import { InfrahubLogo } from "@/shared/components/ui/infrahub-logo";
import { Input } from "@/shared/components/ui/input";
import { classNames } from "@/shared/utils/common";

import { SearchAnywhereTrigger } from "@/entities/navigation/ui/search-anywhere/search-anywhere-trigger";
import { CollapsedSidebarMenuItem } from "@/entities/navigation/ui/sidebar/collapsed-sidebar-menu-item";
import { menuNavigationItemStyle } from "@/entities/navigation/ui/sidebar/styles";

import { BRANCH_NAME, BREADCRUMB, CHILD_PREFIXES, MENU_ITEMS } from "./fixtures";

/** Applies the theme knob the way the app does: the `dark` class on the document element. */
function ThemeKnob({ dark }: { dark: boolean }) {
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return null;
}

type FakeShellProps = {
  collapsed: boolean;
  dark: boolean;
  /** First child of the outer column, above the sidebar and the header. */
  topBar?: ReactNode;
  /** First children of the header, before the time selector. */
  headerLeading?: ReactNode;
  /** Header children placed just before the status icons. */
  headerTrailing?: ReactNode;
  /** Rendered in the sidebar header, under the logo. */
  sidebarBrand?: ReactNode;
};

export function FakeShell({
  collapsed,
  dark,
  topBar,
  headerLeading,
  headerTrailing,
  sidebarBrand,
}: FakeShellProps) {
  return (
    <div className="flex h-screen w-full flex-col bg-background text-foreground">
      <ThemeKnob dark={dark} />
      {topBar}

      <div className="flex min-h-0 w-full flex-1 gap-0.5 p-0.5">
        <FakeSidebar collapsed={collapsed} brand={sidebarBrand} />

        <div className="flex h-full grow flex-col gap-0.5 overflow-hidden">
          <FakeHeader leading={headerLeading} trailing={headerTrailing} />

          <FakeContent />
        </div>
      </div>
    </div>
  );
}

function FakeSidebar({ collapsed, brand }: { collapsed: boolean; brand?: ReactNode }) {
  return (
    <Card
      variant="secondary"
      className={classNames(
        "group w-64 shrink-0 divide-y overflow-hidden data-[state=collapsed]:w-14",
        collapsed && "w-14"
      )}
      data-state={collapsed ? "collapsed" : "expanded"}
    >
      <SidebarHeader>
        <div className="relative h-8 group-data-[state=collapsed]:h-17.5">
          <div
            className={classNames(
              "absolute bottom-0 left-1.75 -m-1 max-w-40 overflow-hidden rounded-md border border-transparent p-0.75",
              "group-data-[state=collapsed]:max-w-8.25"
            )}
          >
            <InfrahubLogo aria-hidden className="h-8 max-w-none" />
            <span className="sr-only">Infrahub home</span>
          </div>

          <Button
            variant="ghost"
            shape="square"
            size="sm"
            aria-label="Toggle sidebar"
            className="absolute top-0 right-0 text-subtle-muted data-hovered:text-subtle group-data-[state=collapsed]:right-0.75"
          >
            <PanelLeftCloseIcon className="size-5" />
          </Button>
        </div>

        {brand}

        <SearchAnywhereTrigger />
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="min-h-25 flex-1">
          <div className="p-2">
            <FakeMenuSection collapsed={collapsed} items={MENU_ITEMS.slice(0, 4)} />
          </div>
        </ScrollArea>
        <Separator />
        <ScrollArea>
          <div className="p-2">
            <FakeMenuSection collapsed={collapsed} items={MENU_ITEMS.slice(4)} />
          </div>
        </ScrollArea>
      </SidebarContent>

      <SidebarFooter className="p-1.5">
        <Button
          variant="ghost"
          size="sm"
          className="h-10 justify-stretch gap-2 data-pressed:scale-100"
          aria-label="Open account menu"
        >
          <Avatar name="Admin" size="sm" />

          <div className="overflow-hidden group-data-[state=collapsed]:hidden">
            <div className="truncate font-medium text-sm">Admin</div>
          </div>

          <EllipsisVerticalIcon className="ml-auto group-data-[state=collapsed]:hidden" />
        </Button>
      </SidebarFooter>
    </Card>
  );
}

function FakeMenuSection({
  collapsed,
  items,
}: {
  collapsed: boolean;
  items: { label: string; icon: string }[];
}) {
  if (collapsed) {
    return (
      <Col className="items-center gap-1">
        {items.map((item) => (
          <CollapsedSidebarMenuItem key={item.label} icon={item.icon} tooltipContent={item.label} />
        ))}
      </Col>
    );
  }

  return (
    <Col className="gap-0">
      {items.map((item) => (
        <div key={item.label} className={menuNavigationItemStyle}>
          <Icon icon={item.icon} className="size-4 shrink-0" />
          <span className="truncate text-sm">{item.label}</span>
        </div>
      ))}
    </Col>
  );
}

function FakeHeader({ leading, trailing }: { leading?: ReactNode; trailing?: ReactNode }) {
  return (
    <Card variant="secondary" className="h-12.5 shrink-0 flex-row items-center gap-2 p-2">
      {leading}

      <div className="inline-flex h-8 shrink-0 items-center overflow-hidden rounded-lg border">
        <Button size="sm" shape="square" variant="ghost" aria-label="Current view time: now">
          <Icon icon="mdi:calendar-clock" className="text-xl" />
        </Button>
      </div>

      <Button variant="outline" size="sm" className="w-64 data-pressed:scale-100">
        <Row className="grow gap-1.5 overflow-hidden">
          <Icon icon="mdi:source-branch" className="shrink-0" />
          <span className="min-w-0 truncate" title={BRANCH_NAME}>
            {BRANCH_NAME}
          </span>
        </Row>

        <Separator orientation="vertical" />

        <ChevronsUpDownIcon className="ml-0.5" />
      </Button>

      <ScrollArea scrollX scrollBarClassName="hidden" className="flex-1">
        <Breadcrumbs>
          {BREADCRUMB.map((crumb) => (
            <Breadcrumb key={crumb}>
              <span className="inline-flex items-center truncate rounded-lg border border-transparent px-2 py-0.5 text-foreground">
                {crumb}
              </span>
            </Breadcrumb>
          ))}
        </Breadcrumbs>
      </ScrollArea>

      {trailing}

      <Button shape="square" variant="outline" size="sm" aria-label="View branch tasks">
        <TasksStatusIcon />
      </Button>

      <Button
        shape="square"
        variant="outline"
        size="sm"
        aria-label="All Git repositories are in sync on this branch"
      >
        <Icon icon="mdi:source-branch" className="size-4" />
      </Button>
    </Card>
  );
}

function FakeContent() {
  return (
    <Card variant="secondary" className="min-h-0 flex-1 overflow-auto">
      <header className="flex items-center border-b p-5">
        <div className="flex flex-1 flex-col gap-0.5 overflow-hidden">
          <div className="flex items-center gap-2 font-bold text-xl">
            <h1 className="truncate">10.240.128.0/17</h1>
            <Badge className="text-sm">IpamIPPrefix</Badge>
          </div>
          <div className="truncate text-sm">Child prefixes of the zurich-west-2 supernet</div>
        </div>
        <Button variant="primary" size="sm">
          Add child prefix
        </Button>
      </header>

      <Card className="m-3 overflow-hidden">
        <CardHeader>Children</CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="text-left text-subtle text-xs">
              <tr className="border-b">
                <th className="px-3 py-2 font-medium">Prefix</th>
                <th className="px-3 py-2 font-medium">Description</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {CHILD_PREFIXES.map((row) => (
                <tr key={row.prefix}>
                  <td className="px-3 py-2 font-mono tabular-nums">{row.prefix}</td>
                  <td className="px-3 py-2 text-foreground-muted">{row.description}</td>
                  <td className="px-3 py-2">
                    <Badge
                      variant={
                        row.status === "active"
                          ? "green"
                          : row.status === "reserved"
                            ? "blue"
                            : "gray-outline"
                      }
                    >
                      {row.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </Card>
  );
}

type FakeLoginProps = {
  dark: boolean;
  /** First child of the page, above everything. */
  topBar?: ReactNode;
  aboveLogo?: ReactNode;
  belowLogo?: ReactNode;
  belowHeading?: ReactNode;
};

export function FakeLogin({ dark, topBar, aboveLogo, belowLogo, belowHeading }: FakeLoginProps) {
  return (
    <div className="flex h-screen w-full flex-col bg-background text-foreground">
      <ThemeKnob dark={dark} />
      {topBar}

      {/* biome-ignore lint/nursery/noTailwindArbitraryValue: no-utility: viewport-relative padding (25vh) has no spacing token */}
      <div className="min-h-0 flex-1 overflow-auto py-[25vh]">
        <div className="m-auto flex w-full max-w-sm flex-col items-center gap-6">
          {aboveLogo}

          <InfrahubLogo className="h-12" />

          {belowLogo}

          <h1 className="font-semibold text-foreground text-xl">Log in to your account</h1>

          {belowHeading}

          <Col className="w-full gap-4">
            <Col className="gap-1">
              <Label htmlFor="proto-username">Username</Label>
              <Input id="proto-username" name="username" autoComplete="username" />
            </Col>
            <Col className="gap-1">
              <Label htmlFor="proto-password">Password</Label>
              <Input
                id="proto-password"
                name="password"
                type="password"
                autoComplete="current-password"
              />
            </Col>
            <Button variant="primary" className="h-10 w-full">
              Log in
            </Button>
          </Col>

          <Button
            variant="ghost"
            className="text-cyan-900 text-sm data-hovered:bg-transparent data-hovered:underline"
          >
            Log in with SSO
          </Button>
        </div>
      </div>
    </div>
  );
}
