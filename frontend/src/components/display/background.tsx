import { MouseEventHandler } from "react";

type tBackground = {
  onClick?: MouseEventHandler;
};

export const Background = ({ onClick, ...propsToPass }: tBackground) => {
  return (
    <div
      className="fixed z-10 inset-0 bg-black bg-opacity-40 transition-opacity"
      onClick={onClick}
      {...propsToPass}
    />
  );
};
