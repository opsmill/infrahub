import { forwardRef, InputHTMLAttributes } from "react";
import { PasswordInput } from "./password-input";
import { CopyToClipboard } from "../buttons/copy-to-clipboard";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const TokenInput = forwardRef<HTMLInputElement, InputProps>((props, ref) => {
  return (
    <div className="flex items-center">
      <PasswordInput {...props} ref={ref} disabled />

      <CopyToClipboard text={props.value as string} className="ml-2" />
    </div>
  );
});
