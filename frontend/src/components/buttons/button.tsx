import { ButtonHTMLAttributes, forwardRef } from "react";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { classNames } from "../../utils/common";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  type?: "button" | "reset" | "submit";
  buttonType?: BUTTON_TYPES;
  className?: string;
  onClick?: Function;
  children?: any;
  disabled?: boolean;
  isLoading?: boolean;
};

export enum BUTTON_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
  MAIN,
  ACTIVE,
  INVISIBLE,
}

// Get default class name and avoid certain class if needed (ex: no rounded button for tabs-button)
const DEFAULT_CLASS = (className?: string, type?: BUTTON_TYPES) => `
  ${className?.includes("rounded") ? "" : "rounded-md"}
  ${className?.includes("border") ? "" : "border border-gray-300"}
  ${className?.includes("shadow") || type === BUTTON_TYPES.INVISIBLE ? "" : "shadow-sm"}
  ${className?.includes("p-") || className?.includes("px-") ? "" : "px-2.5"}
  ${className?.includes("p-") || className?.includes("py-") ? "" : "py-1.5"}
  inline-flex items-center
  text-sm font-semibold
  focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
`;

const getClassName = (type?: BUTTON_TYPES) => {
  switch (type) {
    case BUTTON_TYPES.VALIDATE: {
      return `
        bg-green-500 text-gray-50
        hover:bg-green-400
        disabled:cursor-not-allowed disabled:bg-green-400 disabled:text-gray-100 disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.CANCEL: {
      return `
        bg-red-600 text-gray-50
        hover:bg-red-400
        disabled:cursor-not-allowed disabled:bg-red-400 disabled:text-gray-100 disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.WARNING: {
      return `
        bg-yellow-400 text-gray-800
        hover:bg-yellow-300
        disabled:cursor-not-allowed disabled:bg-yellow-200 disabled:text-gray-600 disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.MAIN: {
      return `
        bg-custom-blue-700 text-custom-white
        hover:bg-custom-blue-500
        disabled:cursor-not-allowed disabled:bg-custom-blue-gray disabled:text-custom-white disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.ACTIVE: {
      return `
        bg-custom-blue-700 text-custom-white cursor-default
        hover:bg-custom-blue-700
        disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-custom-white disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.INVISIBLE: {
      return `
        bg-transparent border-transparent
        disabled:cursor-not-allowed disabled:bg-transparent
      `;
    }
    default: {
      return `
        bg-gray-100 text-gray-900
        hover:bg-gray-200
        disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 disabled:border-slate-200 disabled:shadow-none
      `;
    }
  }
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
export const Button = forwardRef((props: ButtonProps, ref: any) => {
  const { buttonType, type, className = "", onClick, isLoading, children, ...propsToPass } = props;

  const customClassName = getClassName(buttonType);

  const handleClick = (event: any) => {
    if (type !== "submit") {
      event.stopPropagation();
    }

    onClick && onClick(event);
  };

  return (
    <button
      type={type ?? "button"}
      className={classNames(DEFAULT_CLASS(className, buttonType), customClassName, className)}
      {...propsToPass}
      onClick={handleClick}
      disabled={isLoading ? true : propsToPass.disabled}>
      {isLoading && <LoadingScreen size={18} hideText className="px-4" />}
      {!isLoading && children}
    </button>
  );
});
