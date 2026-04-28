import { Icon } from "@iconify-icon/react";

import { Button, type ButtonProps } from "@/shared/components/aria/button";

export const InfoButton = (props: ButtonProps) => (
  <Button variant="ghost" size="xs" shape="circle" {...props}>
    <Icon icon="mdi:information-slab-circle-outline" className="text-custom-blue-800" />
  </Button>
);
