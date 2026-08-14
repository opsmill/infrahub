import type { Meta, StoryObj } from "@storybook/react-vite";

import { Card, CardContent, CardHeader } from "./card";

const meta: Meta = {
  parameters: {
    layout: "padded",
  },
};

export default meta;

export const AllVariants: StoryObj = {
  render: () => (
    <div className="flex flex-col gap-6">
      <Card className="max-w-sm">
        <CardContent className="text-sm text-foreground-muted">
          Card has no default padding. Use CardContent to add the standard p-3 padding for simple
          content.
        </CardContent>
      </Card>

      <Card className="max-w-sm">
        <CardHeader>Section title</CardHeader>
        <CardContent className="text-sm text-foreground-muted">
          CardHeader and CardContent handle their own padding. No overrides needed on Card.
        </CardContent>
      </Card>

      <Card variant="secondary" className="max-w-sm">
        <CardContent className="text-sm text-foreground-muted">
          The secondary surface is for app chrome — header, sidebar, content shell.
        </CardContent>
      </Card>

      <Card variant="panel" className="max-w-sm">
        <CardContent className="text-sm text-foreground-muted">
          The panel surface recedes behind the cards it contains.
        </CardContent>
      </Card>
    </div>
  ),
};
