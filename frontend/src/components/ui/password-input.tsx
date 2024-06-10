import { forwardRef, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { Input, InputProps } from "./input";
import { classNames } from "../../utils/common";
import { Button } from "../buttons/button-primitive";

interface PasswordInputProps extends InputProps {}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);

    return (
      <div className="relative w-full">
        <Input
          ref={ref}
          {...props}
          type={showPassword ? props.type : "password"}
          className={classNames("pr-8 leading-6 h-auto", className)}
        />

        <Button
          onClick={() => setShowPassword((v) => !v)}
          size="icon"
          variant="ghost"
          className="h-10 absolute top-0 end-0 p-3.5 rounded-md hover:bg-transparent">
          <Icon icon={showPassword ? "mdi:eye-off" : "mdi:eye"} />
        </Button>
      </div>
    );
  }
);
