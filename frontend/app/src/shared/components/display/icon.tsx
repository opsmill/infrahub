import { Icon as IconifyIcon } from "@iconify-icon/react";
import type { ComponentProps } from "react";

// iconify-icon registers a visibility observer per element to defer offscreen
// rendering and animations. Our icons are static SVGs, so the observers buy
// nothing and their bookkeeping is measurable on icon-heavy views.
export const Icon = (props: ComponentProps<typeof IconifyIcon>) => (
  <IconifyIcon noobserver {...props} />
);
