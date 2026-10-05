import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  BreadcrumbItem,
  BreadcrumbItemError,
  BreadcrumbItemLoading,
  Breadcrumbs,
} from "./breadcrumbs";

const meta: Meta<typeof Breadcrumbs> = {
  component: Breadcrumbs,
  parameters: {
    layout: "padded",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function AllVariantsRender() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="mb-1 text-subtle-muted text-xs">Links</div>
        <Breadcrumbs>
          <BreadcrumbItem href="/">Home</BreadcrumbItem>
          <BreadcrumbItem href="/objects">Objects</BreadcrumbItem>
          <BreadcrumbItem href="/objects/devices">Devices</BreadcrumbItem>
        </Breadcrumbs>
      </div>

      <div>
        <div className="mb-1 text-subtle-muted text-xs">Buttons</div>
        <Breadcrumbs>
          <BreadcrumbItem onPress={() => {}}>Home</BreadcrumbItem>
          <BreadcrumbItem onPress={() => {}}>Objects</BreadcrumbItem>
          <BreadcrumbItem onPress={() => {}}>Devices</BreadcrumbItem>
        </Breadcrumbs>
      </div>

      <div>
        <div className="mb-1 text-subtle-muted text-xs">Mixed (links + button)</div>
        <Breadcrumbs>
          <BreadcrumbItem href="/">Home</BreadcrumbItem>
          <BreadcrumbItem href="/objects">Objects</BreadcrumbItem>
          <BreadcrumbItem onPress={() => {}}>Current page</BreadcrumbItem>
        </Breadcrumbs>
      </div>

      <div>
        <div className="mb-1 text-subtle-muted text-xs">Loading</div>
        <Breadcrumbs>
          <BreadcrumbItem href="/">Home</BreadcrumbItem>
          <BreadcrumbItemLoading />
        </Breadcrumbs>
      </div>

      <div>
        <div className="mb-1 text-subtle-muted text-xs">Error</div>
        <Breadcrumbs>
          <BreadcrumbItem href="/">Home</BreadcrumbItem>
          <BreadcrumbItemError error={new Error("Failed to fetch")} />
        </Breadcrumbs>
      </div>

      <div>
        <div className="mb-1 text-subtle-muted text-xs">Long content (truncation)</div>
        <div className="w-96">
          <Breadcrumbs>
            <BreadcrumbItem href="/">Home</BreadcrumbItem>
            <BreadcrumbItem href="/objects">Objects</BreadcrumbItem>
            <BreadcrumbItem href="/objects/very-long">
              A very long breadcrumb label that should truncate gracefully when the container is
              narrow
            </BreadcrumbItem>
          </Breadcrumbs>
        </div>
      </div>
    </div>
  );
}

export const AllVariants: Story = {
  render: AllVariantsRender,
};

interface PlaygroundArgs {
  trail: string;
  asLinks: boolean;
  showLoading: boolean;
  showError: boolean;
}

function PlaygroundRender({ trail, asLinks, showLoading, showError }: PlaygroundArgs) {
  const segments = trail
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean);

  return (
    <Breadcrumbs>
      {segments.map((segment, index) =>
        asLinks ? (
          <BreadcrumbItem key={segment} href={`/${segments.slice(0, index + 1).join("/")}`}>
            {segment}
          </BreadcrumbItem>
        ) : (
          <BreadcrumbItem key={segment} onPress={() => {}}>
            {segment}
          </BreadcrumbItem>
        )
      )}
      {showLoading && <BreadcrumbItemLoading />}
      {showError && <BreadcrumbItemError error={new Error("Failed to fetch")} />}
    </Breadcrumbs>
  );
}

export const Playground: StoryObj<PlaygroundArgs> = {
  args: {
    trail: "Home / Objects / Devices",
    asLinks: true,
    showLoading: false,
    showError: false,
  },
  argTypes: {
    trail: { control: "text" },
    asLinks: { control: "boolean" },
    showLoading: { control: "boolean" },
    showError: { control: "boolean" },
  },
  render: PlaygroundRender,
};
