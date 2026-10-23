// PROTOTYPE design-jam commits-tab-pending-badge
import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { getMeaningLabel } from "../scenarios";
import { type CommitsTabProps, ProtoStage } from "../stage";

function CommitsTab({ scenario, to, scrollIntoViewOnActive }: CommitsTabProps) {
  return (
    <LinkTab to={to} scrollIntoViewOnActive={scrollIntoViewOnActive}>
      Commits
      {scenario.condition === "LOADING" ? (
        <Spinner />
      ) : (
        scenario.count !== null && (
          <Badge className="rounded-full font-medium text-subtle">
            {scenario.count}
            <span className="sr-only"> {getMeaningLabel(scenario.meaning)}</span>
          </Badge>
        )
      )}
    </LinkTab>
  );
}

export function TodayRev01({ scenario }: { scenario: string }) {
  return (
    <ProtoStage scenarioOption={scenario} renderCommitsTab={(props) => <CommitsTab {...props} />} />
  );
}
