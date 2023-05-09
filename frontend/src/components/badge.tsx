import { XMarkIcon } from "@heroicons/react/24/outline";
import { classNames } from "../utils/common";

export enum BADGE_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
}

// type BadgeProps = {}

const DEFAULT_CLASS = `
  flex text-sm font-medium mr-2 px-2.5 py-0.5 rounded
`;

const getClasseName = (type: BADGE_TYPES, onClick: Function) => {
  switch (type) {
    case BADGE_TYPES.VALIDATE: {
      return `
        bg-green-400 text-gray-50
        ${onClick ? "cursor-pointer hover:bg-green-200" : ""}
      `;
    }
    case BADGE_TYPES.CANCEL: {
      return `
        bg-red-400 text-gray-50
        ${onClick ? "cursor-pointer hover:bg-red-200" : ""}
      `;
    }
    case BADGE_TYPES.WARNING: {
      return `
        bg-yellow-200 text-gray-800
        ${onClick ? "cursor-pointer hover:bg-yellow-100" : ""}
      `;
    }
    default: {
      return `
        bg-gray-100 text-gray-900
        ${onClick ? "cursor-pointer hover:bg-gray-50" : ""}
      `;
    }
  }
};

export const Badge = (props: any) => {
  const { type, className, children, onDelete, value, onClick } = props;

  const customClassName = getClasseName(type, onClick);

  const handleClick = (event: any) => {
    event.stopPropagation();
    event.preventDefault();

    if (onClick) {
      return onClick(value);
    }

    if (onDelete && value) {
      return onDelete(value);
    }

    return;
  };

  return (
    <span
      className={classNames(
        DEFAULT_CLASS,
        customClassName,
        className,
        onDelete ? "cursor-pointer" : ""
      )}
      onClick={handleClick}>
      {children}

      {onDelete && (
        <div className="ml-2 flex flex-col justify-center">
          <XMarkIcon className="h-4 w-4 text-gray-500" aria-hidden="true" />
        </div>
      )}
    </span>
  );
};
