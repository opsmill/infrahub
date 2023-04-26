import { MouseEventHandler } from "react";

type LinkProps = {
  onClick: MouseEventHandler;
  children: any;
}

export const Link = (props: LinkProps) => {
  return (
    <div onClick={props.onClick} className="cursor-pointer underline">
      {props.children}
    </div>
  );
};