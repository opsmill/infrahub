import type { Meta, StoryObj } from "@storybook/react-vite";
import { XIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "../button/button";
import { Select, SelectItem, SelectList, SelectTrigger } from "../select/select";
import { SortableItem, SortableList } from "./sortable-list";

const meta: Meta<typeof SortableList> = {
  component: SortableList,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

interface Task {
  id: string;
  name: string;
}

const INITIAL_TASKS: Task[] = [
  { id: "1", name: "Design the schema" },
  { id: "2", name: "Build the API" },
  { id: "3", name: "Wire up the UI" },
  { id: "4", name: "Write the tests" },
  { id: "5", name: "Ship it" },
];

/*
 * SortableList is controlled, so the parent always holds the current order.
 * Here it is rendered live beside the list to make onReorder's output tangible.
 */
function DefaultRender() {
  const [tasks, setTasks] = useState(INITIAL_TASKS);

  return (
    <div className="flex items-start gap-6">
      <SortableList aria-label="Tasks" items={tasks} onReorder={setTasks} className="w-72">
        {(task) => (
          <SortableItem id={task.id} textValue={task.name}>
            <span className="flex-1 truncate">{task.name}</span>
          </SortableItem>
        )}
      </SortableList>
      <ol className="w-48 rounded-lg border bg-stone-50 p-2 text-subtle text-xs">
        {tasks.map((task, index) => (
          <li key={task.id} className="flex gap-2 px-1 py-0.5">
            <span className="text-subtle-muted">{index + 1}.</span>
            <span className="truncate">{task.name}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export const Default: Story = {
  render: () => <DefaultRender />,
};

interface Rule {
  id: string;
  name: string;
  action: string;
}

const INITIAL_RULES: Rule[] = [
  { id: "1", name: "Source IP matches", action: "allow" },
  { id: "2", name: "Port is 443", action: "allow" },
  { id: "3", name: "Geo is blocked", action: "deny" },
  { id: "4", name: "Rate limit exceeded", action: "log" },
];

const ACTIONS = [
  { key: "allow", label: "Allow" },
  { key: "deny", label: "Deny" },
  { key: "log", label: "Log only" },
];

/*
 * Each row mixes two independent interactive controls — a Select and a remove
 * button — next to the drag handle. Opening the Select (which is itself a
 * popover) and pressing the button register as presses, not drags, so they work
 * inside a draggable row.
 */
function WithControlsRender() {
  const [rules, setRules] = useState(INITIAL_RULES);

  const setAction = (id: string, action: string) =>
    setRules((current) => current.map((rule) => (rule.id === id ? { ...rule, action } : rule)));

  const remove = (id: string) => setRules((current) => current.filter((rule) => rule.id !== id));

  return (
    <SortableList aria-label="Firewall rules" items={rules} onReorder={setRules} className="w-96">
      {(rule) => (
        <SortableItem id={rule.id} textValue={rule.name}>
          <span className="flex-1 truncate">{rule.name}</span>
          <Select
            aria-label={`Action for ${rule.name}`}
            selectedKey={rule.action}
            onSelectionChange={(key) => setAction(rule.id, String(key))}
          >
            <SelectTrigger className="min-h-8 w-32 py-1" />
            <SelectList items={ACTIONS}>
              {(action) => (
                <SelectItem key={action.key} textValue={action.label}>
                  {action.label}
                </SelectItem>
              )}
            </SelectList>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            shape="square"
            aria-label={`Remove ${rule.name}`}
            onPress={() => remove(rule.id)}
          >
            <XIcon />
          </Button>
        </SortableItem>
      )}
    </SortableList>
  );
}

export const WithControls: Story = {
  render: () => <WithControlsRender />,
};
