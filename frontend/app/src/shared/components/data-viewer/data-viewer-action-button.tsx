import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  Link as AriaLink,
  type LinkProps as AriaLinkProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import { dataViewerActionStyle } from "./data-viewer.styles";

export function DataViewerActionButton({ className, ...props }: AriaButtonProps) {
  return <AriaButton className={classNames(...dataViewerActionStyle, className)} {...props} />;
}

export function DataViewerLinkButton({ className, ...props }: AriaLinkProps) {
  return (
    <AriaLink className={classNames(...dataViewerActionStyle, "leading-4", className)} {...props} />
  );
}
