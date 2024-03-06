import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Retry } from "../../../components/buttons/retry";
import { PieChart } from "../../../components/display/pie-chart";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import {
  CHECKS_LABEL,
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
    if (!stats.length) return false;

    // Can retry if there is no in progress check
    return !!stats.find((stat: any) => stat.name === CHECKS_LABEL.IN_PROGRESS && !!stat.value);
  };

  return (
    <div className="flex justify-center m-4">
      <div className="flex relative">
        <div className="absolute top-1/2 -left-28 transform -translate-y-1/2 flex items-center justify-between p-2">
          <span className="mr-1 text-xs">Retry all:</span>

          <Retry
            onClick={() => handleRetry("all")}
            isLoading={isLoading || !!validatorsInProgress.length}
            isDisabled={!auth?.permissions?.write}
          />
        </div>

        {Object.entries(validatorsCount).map(([kind, data]: [string, any]) => (
          <div key={kind} className="flex items-center justify-center gap-2 p-2">
            <div
              className={classNames(
                "fill",
                "flex flex-col items-center group relative",
                canRetry(data) ? "cursor-pointer" : ""
              )}>
              <PieChart data={data}>
                {canRetry(data) && (
                  <div className="absolute invisible group-hover:visible cursor-pointer">
                    <Retry
                      isLoading={isLoading || !!data.inProgress}
                      isDisabled={!canRetry(data)}
                      className="!hover:bg-transparent"
                      onClick={() => handleRetry(kind)}
                    />
                  </div>
                )}
              </PieChart>

              <span className="text-xs">
                {schemaKindLabel[kind]?.replace("Validator", "").trim()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
