import { gql } from "@apollo/client";
import { ArrowPathIcon, CheckCircleIcon, ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Retry } from "../../../components/buttons/retry";
import { Badge } from "../../../components/display/badge";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import {
  PROPOSED_CHANGES_VALIDATOR_OBJECT,
  VALIDATIONS_ENUM_MAP,
  VALIDATION_STATES,
} from "../../../config/constants";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { runCheck } from "../../../graphql/mutations/diff/runCheck";
import { genericsState } from "../../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../../state/atoms/schemaKindName.atom";
import { getValidatorsStats } from "../../../utils/checks";

type tChecksSummaryProps = {
  validators: any[];
  refetch: Function;
};

export const ChecksSummary = (props: tChecksSummaryProps) => {
  const { validators, refetch } = props;

  const { proposedchange } = useParams();
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [schemaList] = useAtom(genericsState);

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

  return (
    <div className="flex p-4 pb-0 gap-2">
      <div className="flex items-center justify-between p-2 rounded-md bg-custom-white">
        Retry all:{" "}
        <Retry onClick={() => handleRetry("all")} isLoading={!!validatorsInProgress.length} />
      </div>

      <div className="flex-1 flex flex-wrap gap-2">
        {Object.entries(validatorsCount).map(([kind, stats]: [string, any]) => (
          <div
            key={kind}
            className="flex-1 flex items-center justify-between gap-2 p-2 rounded-md bg-custom-white">
            <Badge className="!mr-0">{schemaKindName[kind]}</Badge>

            <div className="flex items-center gap-2">
              <div className="flex items-center">
                {!!stats.failure && <ExclamationCircleIcon className="h-4 w-4 text-red-500" />}

                {!!stats.inProgress && (
                  <ArrowPathIcon className="h-4 w-4 text-orange-500 animate-spin" />
                )}

                {!stats.failure && !stats.inProgress && (
                  <CheckCircleIcon className="h-4 w-4 text-green-500" />
                )}

                <span>
                  {JSON.stringify(stats.success)}/{JSON.stringify(stats.total)}
                </span>
              </div>

              <Retry onClick={() => handleRetry(kind)} isLoading={!!stats.inProgress} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
