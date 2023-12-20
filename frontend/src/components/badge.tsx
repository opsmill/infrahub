import { XMarkIcon } from "@heroicons/react/24/outline";
import { classNames } from "../utils/common";

export enum BADGE_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
  LIGHT,
  DISABLED,
}

// type BadgeProps = {}

const DEFAULT_CLASS = `
  flex font-medium mr-2 last:mr-0 px-2.5 py-0.5 rounded
`;

const getClassName = (type: BADGE_TYPES, onClick: Function, disabled?: boolean) => {
  switch (type) {
    case BADGE_TYPES.VALIDATE: {
      return `
        text-gray-50
        ${disabled ? "bg-green-200" : "bg-green-400"}
        ${onClick && !disabled ? "cursor-pointer hover:bg-green-200" : ""}
      `;
    }
    case BADGE_TYPES.CANCEL: {
      return `
        text-gray-50
        ${disabled ? "bg-red-200" : "bg-red-400"}
        ${onClick && !disabled ? "cursor-pointer hover:bg-red-200" : ""}
      `;
    }
    case BADGE_TYPES.WARNING: {
      return `
        text-gray-800
        ${disabled ? "bg-yellow-50" : "bg-yellow-200"}
        ${onClick && !disabled ? "cursor-pointer hover:bg-yellow-100" : ""}
      `;
    }
    case BADGE_TYPES.LIGHT: {
      return `
        text-gray-800 bg-custom-white
        ${onClick && !disabled ? "cursor-pointer hover:bg-gray-50" : ""}
      `;
    }
    case BADGE_TYPES.DISABLED: {
      return `
        text-gray-800
        ${disabled ? "bg-gray-100" : "bg-gray-300"}
        ${onClick && !disabled ? "cursor-pointer hover:bg-gray-50" : ""}
      `;
    }
    default: {
      return `
        text-gray-900
        ${disabled ? "bg-gray-50" : "bg-gray-100"}
        ${onClick && !disabled ? "cursor-pointer hover:bg-gray-50" : ""}
      `;
    }
  }
};

export const Badge = (props: any) => {
  const { type, className, children, onDelete, value, onClick, disabled } = props;

  const customClassName = getClassName(type, onClick || onDelete, disabled);

  const handleClick = (event: any) => {
    event.stopPropagation();
    event.preventDefault();

    if (disabled) {
      return;
    }

    if (onClick) {
      return onClick(value);
    }

    if (onDelete) {
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
        onDelete && !disabled ? "cursor-pointer" : ""
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
