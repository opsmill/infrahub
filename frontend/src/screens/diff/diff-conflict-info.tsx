import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";
import { useContext } from "react";
import { Tooltip, TooltipPosition } from "../../components/tooltip";
import { DiffContext } from "./data-diff";

type tDataDiffConflictInfo = {
  path: string;
};

export const DataDiffConflictInfo = (props: tDataDiffConflictInfo) => {
  const { path } = props;

  const { checksDictionnary } = useContext(DiffContext);

  if (!path || !checksDictionnary) {
    return null;
  }

  const keys = Object.keys(checksDictionnary);

  const matchingKey = keys.find((key: string) => key.startsWith(path));

  if (!matchingKey) {
    return null;
  }

  // const messages = checksDictionnary[matchingKey]
  //   .map((data: any) => data?.message?.value)
  //   .filter(Boolean);

  const messages = ["Some info here", "More info there"];

  if (!messages.length) {
    return null;
  }

  const message = (
    <>
      {messages.map((message: string) => (
        <>
          {message}
          <br />
        </>
      ))}
    </>
  );

  return (
    <div className="absolute right-0 hidden group-hover:block">
      <div className="cursor-pointer hidden group-hover:block">
        <Tooltip message={message} position={TooltipPosition.LEFT}>
          <QuestionMarkCircleIcon className="h-6 w-6 text-custom-blue-green" aria-hidden="true" />
        </Tooltip>
      </div>
    </div>
  );
};
