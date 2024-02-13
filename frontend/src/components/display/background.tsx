import { MouseEventHandler } from "react";
import { classNames } from "../../utils/common";

type tBackground = {
  onClick?: MouseEventHandler;
  className?: string;
};

export const Background = ({ onClick, className = "", ...propsToPass }: tBackground) => {
  return (
    <div
      className={classNames(
        "fixed z-10 inset-0 bg-opacity-40 transition-opacity",
        className?.includes("bg-") ? "" : "bg-black",
        className
      )}
      onClick={onClick}
      {...propsToPass}
    />
  );
};
