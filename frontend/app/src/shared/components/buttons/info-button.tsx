import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";
import { forwardRef } from "react";

export interface MoreButtonProps extends ButtonProps {}

export const InfoButton = forwardRef<HTMLButtonElement, MoreButtonProps>((props, ref) => (
  <Button variant="ghost" size="icon" {...props} ref={ref}>
    <Icon icon="mdi:information-slab-circle-outline" className="text-custom-blue-800" />
  </Button>
));
