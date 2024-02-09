import { XMarkIcon } from "@heroicons/react/24/outline";
import { classNames } from "../../utils/common";
import { Circle } from "./circle";

export enum CIRCLE_BADGE_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
  LIGHT,
}

// type BadgeProps = {}

const DEFAULT_CLASS = "flex items-center text-sm font-medium mr-2 px-2.5 py-0.5 rounded";

const getClassName = (type?: CIRCLE_BADGE_TYPES, onClick?: Function) => {
  switch (type) {
    case CIRCLE_BADGE_TYPES.VALIDATE: {
      return `
        bg-green-300 text-gray-50
        ${onClick ? "cursor-pointer hover:bg-green-400" : ""}
      `;
    }
    case CIRCLE_BADGE_TYPES.CANCEL: {
      return `
        bg-red-300 text-gray-50
        ${onClick ? "cursor-pointer hover:bg-red-600" : ""}
      `;
    }
    case CIRCLE_BADGE_TYPES.WARNING: {
      return `
        bg-yellow-200 text-gray-800
        ${onClick ? "cursor-pointer hover:bg-yellow-100" : ""}
      `;
    }
    case CIRCLE_BADGE_TYPES.LIGHT: {
      return `
        bg-custom-white text-gray-800
        ${onClick ? "cursor-pointer hover:bg-gray-50" : ""}
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

const getCircleClasseName = (type?: CIRCLE_BADGE_TYPES, onClick?: Function) => {
  switch (type) {
    case CIRCLE_BADGE_TYPES.VALIDATE: {
      return `
        fill-green-500
        ${onClick ? "" : ""}
      `;
    }
    case CIRCLE_BADGE_TYPES.CANCEL: {
      return `
        fill-red-500
        ${onClick ? "" : ""}
      `;
    }
    case CIRCLE_BADGE_TYPES.WARNING: {
      return `
        fill-yellow-500
        ${onClick ? "" : ""}
      `;
    }
    case CIRCLE_BADGE_TYPES.LIGHT: {
      return `
        fill-gray-500
        ${onClick ? "" : ""}
      `;
    }
    default: {
      return `
        fill-gray-600
        ${onClick ? "" : ""}
      `;
    }
  }
};

type tBadgeCircleProps = {
  type?: CIRCLE_BADGE_TYPES;
  className?: string;
  children: any;
  onDelete?: Function;
  value?: any;
  onClick?: Function;
};

export const BadgeCircle = (props: tBadgeCircleProps) => {
  const { type, className = "", children, onDelete, value, onClick } = props;

  const customClassName = getClassName(type, onClick || onDelete);
  const customCircleClassName = getCircleClasseName(type, onClick || onDelete);

  const handleClick = (event: any) => {
    // Do not block click if there is no onClick
    if (!onClick) return;

    event.stopPropagation();
    event.preventDefault();

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
        onDelete ? "cursor-pointer" : ""
      )}
      onClick={handleClick}>
      <Circle className={customCircleClassName} />

      {children}

      {onDelete && (
        <div className="ml-2 flex flex-col justify-center">
          <XMarkIcon className="h-4 w-4 text-gray-500" aria-hidden="true" />
        </div>
      )}
    </span>
  );
};
