import { QSP } from "@/config/qsp";
import { diffContent, getBadgeType } from "@/entities/diff/diff";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/display/badge";
import { Id } from "@/shared/components/ui/id";
import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { ArrowTopRightOnSquareIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

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
                  className={classNames("flex-1 grid grid-cols-2 gap-2 p-2 rounded-md", className)}
                >
                  <div className="flex items-center">
                    <Badge className="mr-2">{branch}</Badge>

                    <Badge className="mr-2" type={getBadgeType(action)}>
                      {action?.toUpperCase()}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    {diffContent[action](property)}

                    <div className="ml-2">
                      <Tooltip enabled content={"Open object in new tab"}>
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
    </div>
  );
};
