import { useAtomValue } from "jotai";
import { useParams } from "react-router";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Retry } from "@/shared/components/buttons/retry";
import { PieChart } from "@/shared/components/display/pie-chart";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import {
  CHECKS_LABEL,
  PROPOSED_CHANGES_VALIDATOR_OBJECT,
  VALIDATIONS_ENUM_MAP,
} from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { proposedChangeValidatorsKeys } from "@/entities/diff/domain/diff.query-keys";
import { useRunCheckMutation } from "@/entities/diff/domain/run-check.mutation";
import { getValidatorsStats } from "@/entities/proposed-changes/ui/checks";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";

type ChecksSummaryProps = {
  validators: any[];
  isLoading: boolean;
};

export const ChecksSummary = (props: ChecksSummaryProps) => {
  const { isLoading, validators } = props;

  const { proposedChangeId } = useParams();
  const schemaKindLabel = useAtomValue(schemaKindLabelState);
  const schemaList = useAtomValue(genericSchemasAtom);
  const { isAuthenticated } = useAuth();
  const { mutate, isPending } = useRunCheckMutation();

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_VALIDATOR_OBJECT);

  const validatorKinds = schemaData?.used_by ?? [];

  const validatorsCount = validatorKinds.reduce((acc, kind) => {
    const relatedValidators = validators.filter((validator: any) => validator.__typename === kind);

    return { ...acc, [kind]: getValidatorsStats(relatedValidators) };
  }, {});

  const handleRetry = async (validator: string) => {
    mutate(
      {
        proposedChangeId: proposedChangeId!,
        checkType: VALIDATIONS_ENUM_MAP[validator]!,
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({
            queryKey: proposedChangeValidatorsKeys.allWithinProposedChange(proposedChangeId!),
          });
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Checks are running" />);
        },
      }
    );
  };

  const canRetry = (stats: any) => {
    // Can't retry if there is no check
    if (!stats.length) return false;

    // Can't retry if it's empty
    if (stats.length === 1 && stats.find((stat: any) => stat.name === CHECKS_LABEL.EMPTY)) {
      return false;
    }

    // Can retry if there is no in progress check
    return !stats.find((stat: any) => stat.name === CHECKS_LABEL.IN_PROGRESS && !!stat.value);
  };

  return (
    <div className="m-4 flex justify-center" data-testid="checks-summary">
      <div className="relative flex flex-col-reverse items-center">
        <div className="flex items-center justify-between p-2 lg:absolute lg:top-1/2 lg:-left-28 lg:-translate-y-1/2 lg:transform">
          <Button
            onClick={() => handleRetry("all")}
            disabled={!isAuthenticated}
            variant="ghost"
            className="gap-1 hover:bg-neutral-200"
          >
            Retry all
            <Retry isLoading={isPending || isLoading} isDisabled={isPending || isLoading} />
          </Button>
        </div>

        <div className="flex">
          {!Object.entries(validatorsCount).length && <LoadingIndicator />}

          {Object.entries(validatorsCount).map(([kind, data]: [string, any]) => (
            <div key={kind} className="flex items-center justify-center gap-2 p-2">
              <div className={"group relative flex flex-col items-center"}>
                <PieChart data={data} />

                <div className="flex h-6 items-center justify-center">
                  <span
                    className={classNames(
                      "text-xs",
                      canRetry(data) && "absolute text-xs group-hover:invisible"
                    )}
                  >
                    {(schemaKindLabel[kind] ?? kind)?.replace("Validator", "").trim()}
                  </span>

                  {canRetry(data) && (
                    <div className="invisible absolute group-hover:visible">
                      <Retry
                        isLoading={isPending || isLoading || !!data.inProgress}
                        isDisabled={!canRetry(data)}
                        onClick={() => canRetry(data) && handleRetry(kind)}
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
