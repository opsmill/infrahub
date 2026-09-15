import type {
  TabsContentProps,
  TabsListProps,
  TabsTriggerProps,
} from "@/shared/components/ui/tabs";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { classNames } from "@/shared/utils/common";

/**
 * Tabs that switch how a single form field is filled in — typically "provide the value yourself"
 * versus "allocate it from a resource pool". Thin wrappers over the `ui/tabs` primitives, in the
 * same spirit as `PopoverTabs*`: they pin the `segmented` variant and the panel's top spacing so
 * every pool-backed field gets the same strip without restating it, and so the strip cannot drift
 * apart between fields.
 *
 * Spacing follows the label/input rhythm the other fields use (`space-y-2`), so a panel's first
 * control sits the same distance from its label as in a plain field.
 *
 * The panel closes the outline the strip opens: an active trigger draws its left, top and right
 * edges and leaves the bottom open, so the two must touch for the field to read as one region.
 */
export const FieldTabs = Tabs;

export const FieldTabsList = ({ className, ...props }: TabsListProps) => (
  // The strip owns its gap from the label, so the root can leave the panel flush against it.
  <TabsList variant="field" className={classNames("mt-2", className)} {...props} />
);

export const FieldTabsTrigger = ({ className, ...props }: TabsTriggerProps) => (
  <TabsTrigger variant="field" className={className} {...props} />
);

export const FieldTabsContent = ({ className, ...props }: TabsContentProps) => (
  <TabsContent
    className={classNames(
      "space-y-2 rounded-b-md border-border border-x border-b px-3 pt-3 pb-3",
      className
    )}
    {...props}
  />
);
