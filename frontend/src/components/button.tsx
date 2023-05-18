import { forwardRef } from "react";
import { classNames } from "../utils/common";

type ButtonProps = {
  type?: "button" | "reset" | "submit";
  buttonType?: BUTTON_TYPES;
  className?: string;
  onClick?: Function;
  children?: any;
  disabled?: boolean;
};

export enum BUTTON_TYPES {
  VALIDATE,
  CANCEL,
  WARNING,
  MAIN,
  ACTIVE,
}

// Get default class name and avoid certain class if needed (ex: no rounded button for tabs-button)
const DEFAULT_CLASS = (className?: string) => `
  ${className?.includes("rounded") ? "" : "rounded-md"}
  ${className?.includes("border") ? "" : "border border-gray-300"}
  py-1.5 px-2.5
  inline-flex items-center gap-x-1.5
  text-sm font-semibold
  focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
  shadow-sm
`;

const getClasseName = (type?: BUTTON_TYPES) => {
  switch (type) {
    case BUTTON_TYPES.VALIDATE: {
      return `
        bg-green-600 text-gray-50
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
        bg-blue-500 text-white
        hover:bg-blue-600
        disabled:cursor-not-allowed disabled:bg-blue-200 disabled:text-white disabled:border-slate-200 disabled:shadow-none
      `;
    }
    case BUTTON_TYPES.ACTIVE: {
      return `
        bg-gray-500 text-white cursor-default
        hover:bg-gray-500
        disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-white disabled:border-slate-200 disabled:shadow-none
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
  const { buttonType, type, className = "", onClick, ...propsToPass } = props;

  const customClassName = getClasseName(buttonType);

  const handleClick = (event: any) => {
    if (type !== "submit") {
      event.stopPropagation();
    }

    onClick && onClick(event);
  };

  return (
    <button
      type={type ?? "button"}
      className={classNames(DEFAULT_CLASS(className), customClassName, className)}
      {...propsToPass}
      onClick={handleClick}>
      {props.children}
    </button>
  );
});
