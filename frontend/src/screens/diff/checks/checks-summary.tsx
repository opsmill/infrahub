import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Retry } from "../../../components/buttons/retry";
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
import { schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { getValidatorsStats } from "../../../utils/checks";
import { classNames } from "../../../utils/common";

type tChecksSummaryProps = {
  validators: any[];
  refetch: Function;
};

export const ChecksSummary = (props: tChecksSummaryProps) => {
  const { validators, refetch } = props;

  const { proposedchange } = useParams();
  const schemaKindName = useAtomValue(schemaKindNameState);
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

    // Can retry if there is a failure to re run
    if (stats.failure && !stats.inProgress) return true;

    return false;
  };

  const getBgColor = (stats: any) => {
    if (!stats.total) return "bg-gray-200";

    if (stats.failure) return "bg-red-400";

    if (stats.inProgress) return "bg-orange-400";

    return "bg-green-400";
  };

  return (
    <div className="flex p-4 pb-0 gap-2">
      <div className="flex items-center justify-between p-2 rounded-md ">
        <span className="mr-1">Retry all:</span>

        <Retry
          onClick={() => handleRetry("all")}
          isLoading={!!validatorsInProgress.length}
          isDisabled={!auth?.permissions?.write}
        />
      </div>

      <div className="flex-1 flex flex-wrap gap-2">
        {Object.entries(validatorsCount).map(([kind, stats]: [string, any]) => (
          <div key={kind} className="flex-1 flex items-center justify-center gap-2 p-2">
            <div className="flex items-center gap-2">
              <div
                className={classNames(
                  "flex flex-col items-center group relative",
                  canRetry(stats) ? "cursor-pointer" : ""
                )}
                onClick={() => handleRetry(kind)}>
                <div
                  className={classNames(
                    "flex items-center justify-center w-16 h-16  rounded-full",
                    getBgColor(stats)
                  )}>
                  <span
                    className={classNames(
                      "absolute",
                      canRetry(stats) ? "group-hover:invisible" : ""
                    )}>
                    {JSON.stringify(stats.success)}/{JSON.stringify(stats.total)}
                  </span>

                  {canRetry(stats) && (
                    <div className="absolute invisible group-hover:visible">
                      <Retry
                        isLoading={!!stats.inProgress}
                        isDisabled={!canRetry(stats)}
                        className="!hover:bg-transparent"
                      />
                    </div>
                  )}
                </div>

                <span className="text-xs">{schemaKindName[kind]}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
