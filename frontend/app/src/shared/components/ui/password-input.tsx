import { Icon } from "@iconify-icon/react";
import React from "react";

import { Button } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import { Input, type InputProps } from "./input";

interface PasswordInputProps extends InputProps {}

export function PasswordInput({ className, ref, ...props }: PasswordInputProps) {
  const [showPassword, setShowPassword] = React.useState(false);

  return (
    <div className="relative w-full">
      <Input
        ref={ref}
        {...props}
        type={showPassword ? props.type : "password"}
        className={classNames("pr-8", className)}
      />

      <Button
        onClick={() => setShowPassword((v) => !v)}
        size="icon"
        variant="ghost"
        className="absolute end-0 top-0 h-10 rounded-md p-3.5 hover:bg-transparent"
      >
        <Icon icon={showPassword ? "mdi:eye-off" : "mdi:eye"} />
      </Button>
    </div>
  );
}
