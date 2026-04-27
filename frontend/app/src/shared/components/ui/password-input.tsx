import { EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";

import { Button } from "@/shared/components/aria/button";
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
        onPress={() => setShowPassword((v) => !v)}
        size="icon"
        variant="ghost"
        className="absolute top-0 right-0 h-10 rounded-md p-3.5 data-hovered:bg-transparent"
      >
        {showPassword ? <EyeIcon className="size-3.5" /> : <EyeOffIcon className="size-3.5" />}
      </Button>
    </div>
  );
}
