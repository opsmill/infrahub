import React from "react";

import { Input, type InputProps } from "@/shared/components/ui/input";
import { classNames } from "@/shared/utils/common";

interface LabeledInputProps extends InputProps {
  label: React.ReactNode;
  labelClassName?: string;
}

export function LabeledInput({ label, labelClassName, ...props }: LabeledInputProps) {
  const id = React.useId();
  return (
    <div className={classNames("flex flex-col gap-1 text-sm", labelClassName)}>
      <label htmlFor={id}>{label}</label>
      <Input id={id} {...props} />
    </div>
  );
}
