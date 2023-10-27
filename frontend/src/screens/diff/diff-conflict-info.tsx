import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";
import { useContext } from "react";
import { Id } from "../../components/id";
import { POPOVER_SIZE, PopOver } from "../../components/popover";
import { Check } from "./checks/check";
import { DiffContext } from "./data-diff";

type tDataDiffConflictInfo = {
  path: string;
};

const getIdFromPath = (path: string) => {
  const id = path?.split("/")?.[1];

  return id;
};

export const DataDiffConflictInfo = (props: tDataDiffConflictInfo) => {
  const { path } = props;

  const id = getIdFromPath(path);

  const { checksDictionnary } = useContext(DiffContext);

  if (!path || !checksDictionnary) {
    return null;
  }

  const keys = Object.keys(checksDictionnary);

  const matchingKey = keys.find((key: string) => key.startsWith(path));

  if (!matchingKey) {
    return null;
  }

  const checks = checksDictionnary[matchingKey];

  const MoreButton = (
    <div className="p-1 cursor-pointer">
      <QuestionMarkCircleIcon className="h-5 w-5 text-custom-blue-green" aria-hidden="true" />
    </div>
  );

  const renderContent = () => {
    return (
      <div>
        <div className="flex mb-2">
          <Id id={id} />
        </div>

        <div className="grid grid-cols-1 gap-4">
          {checks.map((check: any, index: number) => (
            <Check key={index} id={check?.id} />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="absolute right-0 font-normal">
      <div className="cursor-pointer">
        <PopOver buttonComponent={MoreButton} size={POPOVER_SIZE.LARGE} className="bg-gray-100">
          {renderContent}
        </PopOver>
      </div>
    </div>
  );
};
