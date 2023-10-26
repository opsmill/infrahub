import { ArrowTopRightOnSquareIcon } from "@heroicons/react/24/outline";
import { Badge } from "../../../components/badge";
import { Link } from "../../../components/link";
import { Tooltip, TooltipPosition } from "../../../components/tooltip";
import { classNames } from "../../../utils/common";
import { diffContent, getBadgeType } from "../../../utils/diff";
import { constructPath } from "../../../utils/fetch";
import { getObjectDetailsUrl } from "../../../utils/objects";
import { getNodeClassName } from "../data-diff-node";

export const Conflict = (props: any) => {
  const { changes, kind, name, node_id } = props;

  return (
    <div>
      <div className="flex items-center mb-2">
        <Badge className="mr-2">{kind}</Badge>

        <span className="font-bold">{name}</span>
      </div>

      <div>
        {changes.map((change: any, index: number) => {
          const { action, branch } = change;

          const property = {
            value: change,
          };

          const url = constructPath(getObjectDetailsUrl(node_id, kind), [["branch", branch]]);

          return (
            <div
              key={index}
              className={classNames(
                "flex items-center mb-2 last:mb-0 p-2 rounded-md",
                getNodeClassName([], branch, "false")
              )}>
              <Badge className="mr-2" type={getBadgeType(action)}>
                {action?.toUpperCase()}
              </Badge>

              <div className="flex items-center justify-center">
                {diffContent[action](property)}
              </div>

              <div className="ml-2">
                <Tooltip message={"Open object in new tab"} position={TooltipPosition.RIGHT}>
                  <Link to={url} target="_blank">
                    <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                  </Link>
                </Tooltip>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
