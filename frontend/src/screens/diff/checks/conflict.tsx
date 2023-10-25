import { Badge } from "../../../components/badge";
import { classNames } from "../../../utils/common";
import { diffContent, getBadgeType } from "../../../utils/diff";
import { getNodeClassName } from "../data-diff-node";

export const Conflict = (props: any) => {
  const { changes, kind, name } = props;

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
            </div>
          );
        })}
      </div>
    </div>
  );
};
