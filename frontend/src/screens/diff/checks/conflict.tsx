import { gql } from "@apollo/client";
import { ArrowTopRightOnSquareIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";
import { ToggleButtons } from "../../../components/buttons/toggle-buttons";
import { Badge } from "../../../components/display/badge";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { Id } from "../../../components/utils/id";
import { Link } from "../../../components/utils/link";
import { Tooltip, TooltipPosition } from "../../../components/utils/tooltip";
import { DATA_CHECK_OBJECT } from "../../../config/constants";
import { QSP } from "../../../config/qsp";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../../graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { datetimeAtom } from "../../../state/atoms/time.atom";
import { classNames } from "../../../utils/common";
import { diffContent, getBadgeType } from "../../../utils/diff";
import { constructPath } from "../../../utils/fetch";
import { getObjectDetailsUrl } from "../../../utils/objects";
import { stringifyWithoutQuotes } from "../../../utils/string";
import { getNodeClassName } from "../data-diff-node";

const renderConflict = {
  attribute_value: (name: string) => {
    return name;
  },
  attribute_property: (name: string, propertyName: string) => {
    return (
      <div className="flex items-center">
        <span>{name}</span>

        <ChevronRightIcon className="w-4 h-4 mx-2" />

        <span>{propertyName}</span>
      </div>
    );
  },
  relationship_one_value: (name: string) => {
    return name;
  },
  relationship_one_property: (name: string, propertyName: string) => {
    return (
      <div className="flex items-center">
        <span>{name}</span>

        <ChevronRightIcon className="w-4 h-4 mx-2" />

        <span>{propertyName}</span>
      </div>
    );
  },
};

export const Conflict = (props: any) => {
  const { check, id, changes, kind, name, node_id, property_name, change_type, refetch } = props;

  const { keep_branch } = check;

  const currentBranch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);

  const handleAccept = async (conflictValue: string) => {
    try {
      setIsLoading(true);

      const newValue = conflictValue === keep_branch?.value ? null : conflictValue;

      const newData = {
        id,
        keep_branch: {
          value: newValue,
        },
      };

      const mustationString = updateObjectWithId({
        kind: DATA_CHECK_OBJECT,
        data: stringifyWithoutQuotes(newData),
      });

      const mutation = gql`
        ${mustationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: currentBranch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Conflict marked as resovled" />);

      setIsLoading(false);

      if (refetch) {
        refetch();
      }
    } catch (error) {
      console.error("Error while updateing the conflict: ", error);
      setIsLoading(false);
    }
  };

  const tabs = [
    {
      label: "target",
      isActive: keep_branch?.value === "target",
      onClick: () => handleAccept("target"),
    },
    {
      label: "source",
      isActive: keep_branch?.value === "source",
      onClick: () => handleAccept("source"),
    },
  ];

  return (
    <div>
      <div className="flex items-center mb-2">
        <Badge className="mr-2">{kind}</Badge>

        <Id id={node_id} kind={kind} />

        <div>{renderConflict[change_type] && renderConflict[change_type](name, property_name)}</div>
      </div>

      <div>
        {changes &&
          changes.map((change: any, index: number) => {
            const { action, branch } = change;

            const property = {
              value: change,
            };

            const url = constructPath(getObjectDetailsUrl(node_id, kind), [
              { name: QSP.BRANCH, value: branch },
            ]);

            const isSelected =
              (keep_branch?.value === "target" && branch === "main") ||
              (keep_branch?.value === "source" && branch !== "main");

            const className = isSelected ? "border-2 border-gray-500" : "";

            return (
              <div key={index} className="flex items-center mb-2 last:mb-0">
                <div
                  className={classNames(
                    "flex-1 grid grid-cols-2 gap-2 p-2 rounded-md",
                    className,
                    getNodeClassName([], branch, "false")
                  )}>
                  <div className="flex items-center">
                    <Badge className="mr-2">{branch}</Badge>

                    <Badge className="mr-2" type={getBadgeType(action)}>
                      {action?.toUpperCase()}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    {diffContent[action](property)}

                    <div className="ml-2">
                      <Tooltip message={"Open object in new tab"} position={TooltipPosition.LEFT}>
                        <Link to={url} target="_blank">
                          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                        </Link>
                      </Tooltip>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
      </div>

      {keep_branch && (
        <div className="flex items-center">
          Accept: <ToggleButtons tabs={tabs} isLoading={isLoading} />
        </div>
      )}
    </div>
  );
};
