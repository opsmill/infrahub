// PROTOTYPE — "Object layout" direction: same layers, cards and colours as the object details page
// (Content.Card → header row → tabs → body Card → Cards with CardHeader). Merge isn't gated: the
// branch actions are today's inline buttons, below the repositories they depend on.
import { Button, LinkButton } from "@infrahub/ui";
import { CheckIcon } from "lucide-react";
import { toast } from "react-toastify";

import { Col, Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { GitRepositoriesCard } from "./git-repositories-card";
import { fakeMerge } from "./merge-rail";
import { Attributes, type VariantProps } from "./shared";
import { TasksTable } from "./tasks-table";

const info = (m: string) => toast(<Alert type={ALERT_TYPES.INFO} message={`${m} (prototype)`} />);

export function ObjectVariant({
  data,
  locate,
  onLocate,
  card,
  tasksPage,
  onTasksPage,
}: VariantProps) {
  const { branch } = data;

  return (
    <Col className="gap-3 p-3">
      <Attributes branch={branch} title="Details" />
      <GitRepositoriesCard {...card} objectStyle data={data} locate={locate} onLocate={onLocate} />
      <Row className="flex-wrap">
        <Button
          variant="active"
          className="flex items-center gap-2"
          isDisabled={data.status === "loading"}
          onPress={() => fakeMerge(branch.name)}
        >
          Merge <CheckIcon className="size-4" />
        </Button>
        <LinkButton href="/proposed-changes/new" variant="outline">
          Propose change
        </LinkButton>
        <Button variant="outline" onPress={() => info("Rebase")}>
          Rebase
        </Button>
        <Button variant="outline" onPress={() => info("Validate")}>
          Validate
        </Button>
        <Button variant="danger-outline" onPress={() => info("Delete")}>
          Delete
        </Button>
      </Row>
      <TasksTable
        objectStyle
        tasks={data.tasks}
        page={tasksPage}
        onPageChange={onTasksPage}
        locate={locate}
        loading={data.status === "loading"}
        unavailable={data.tasksUnknown}
      />
    </Col>
  );
}
