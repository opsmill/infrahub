import type {
  TabsContentProps,
  TabsListProps,
  TabsTriggerProps,
} from "@/shared/components/ui/tabs";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { classNames } from "@/shared/utils/common";

/**
 * An active trigger draws its left, top and right edges and leaves the bottom open, so the panel
 * must stay flush against the strip for the field to read as one region.
 */
export const FieldTabs = Tabs;

export const FieldTabsList = ({ className, ...props }: TabsListProps) => (
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
