import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Retry } from "../../../components/buttons/retry";
import { RadialProgress } from "../../../components/display/radial-progress";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import {
  PROPOSED_CHANGES_VALIDATOR_OBJECT,
  VALIDATIONS_ENUM_MAP,
  VALIDATION_STATES,
} from "../../../config/constants";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { runCheck } from "../../../graphql/mutations/diff/runCheck";
import { useAuth } from "../../../hooks/useAuth";
import { genericsState } from "../../../state/atoms/schema.atom";
import { schemaKindLabelState } from "../../../state/atoms/schemaKindLabel.atom";
import { getValidatorsStats } from "../../../utils/checks";
import { classNames } from "../../../utils/common";

type tChecksSummaryProps = {
  validators: any[];
  isLoading: boolean;
  refetch: Function;
};

export const ChecksSummary = (props: tChecksSummaryProps) => {
  const { isLoading, validators, refetch } = props;

  const { proposedchange } = useParams();
  const schemaKindLabel = useAtomValue(schemaKindLabelState);
  const schemaList = useAtomValue(genericsState);
  const auth = useAuth();

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_VALIDATOR_OBJECT);

  const validatorKinds = schemaData?.used_by ?? [];

  const validatorsCount = validatorKinds.reduce((acc, kind) => {
    const relatedValidators = validators.filter((validator: any) => validator.__typename === kind);

    return { ...acc, [kind]: getValidatorsStats(relatedValidators) };
  }, {});

  const validatorsInProgress = validators.filter(
    (validator: any) => validator?.state?.value === VALIDATION_STATES.IN_PROGRESS
  );

  const handleRetry = async (validator: string) => {
    const runParams = {
      id: proposedchange,
      check_type: VALIDATIONS_ENUM_MAP[validator],
    };

    const mustationString = runCheck(runParams);

    const mutation = gql`
      ${mustationString}
    `;

    const result = await graphqlClient.mutate({ mutation });

    refetch();

    if (result?.data?.CoreProposedChangeRunCheck?.ok) {
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Checks are running" />);
    }
  };

  const canRetry = (stats: any) => {
    // Can't retry if there is no check
    if (!stats.total) return false;

    // Can retry if there is a failure to re-run
    if (stats.failure && !stats.inProgress) return true;

    return false;
  };

  const getProgressColor = (stats: any) => {
    if (!stats.total)
      return {
        bg: "text-gray-200",
        fg: "text-gray-200",
      };

    if (stats.failure)
      return {
        bg: "text-red-100",
        fg: "text-red-400",
      };

    if (stats.inProgress)
      return {
        bg: "text-orange-100",
        fg: "text-orange-400",
      };

    return {
      bg: "text-green-400",
      fg: "text-green-400",
    };
  };

  const getProgressStat = (stats: any) => {
    if (!stats.total) return 0;

    if (stats.inProgress) {
      return (stats.inProgress ?? 0) / stats.total;
    }

    return stats.success / stats.total;
  };

  const getProgressText = (stats: any) => {
    return `${stats.success ?? stats.inProgress ?? 0} / ${stats.total ?? 0}`;
  };

  return (
    <div className="flex justify-center">
      <div className="flex relative">
        <div className="absolute top-1/2 -left-28 transform -translate-y-1/2 flex items-center justify-between p-2">
          <span className="mr-1">Retry all:</span>

          <Retry
            onClick={() => handleRetry("all")}
            isLoading={isLoading || !!validatorsInProgress.length}
            isDisabled={!auth?.permissions?.write}
          />
        </div>

        {Object.entries(validatorsCount).map(([kind, stats]: [string, any]) => (
          <div key={kind} className="flex items-center justify-center gap-2 p-2">
            <div
              className={classNames(
                "flex flex-col items-center group relative",
                canRetry(stats) ? "cursor-pointer" : ""
              )}
              onClick={() => handleRetry(kind)}>
              <RadialProgress
                percent={getProgressStat(stats)}
                bgColor={getProgressColor(stats).bg}
                color={getProgressColor(stats).fg}>
                <span
                  className={classNames(
                    "absolute",
                    canRetry(stats) ? "group-hover:invisible" : ""
                  )}>
                  {getProgressText(stats)}
                </span>

                {canRetry(stats) && (
                  <div className="absolute invisible group-hover:visible">
                    <Retry
                      isLoading={isLoading || !!stats.inProgress}
                      isDisabled={!canRetry(stats)}
                      className="!hover:bg-transparent"
                    />
                  </div>
                )}
              </RadialProgress>

              <span className="text-xs">
                {schemaKindLabel[kind].replace("Validator", "").trim()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
