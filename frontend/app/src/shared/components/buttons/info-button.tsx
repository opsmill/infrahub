import { Icon } from "@iconify-icon/react";
import type React from "react";

import { Button, type ButtonProps } from "@/shared/components/ui/button";

interface MoreButtonProps extends ButtonProps {
  ref?: React.Ref<HTMLButtonElement>;
}

export const InfoButton = ({ ref, ...props }: MoreButtonProps) => (
  <Button variant="ghost" size="icon" {...props} ref={ref}>
    <Icon icon="mdi:information-slab-circle-outline" className="text-custom-blue-800" />
  </Button>
);
