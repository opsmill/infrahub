import { cn } from "tailwind-variants";

// Mirror of frontend/app/src/shared/components/aria/style-rac.ts.
// Keep both copies in sync until the app's aria/* components migrate to @infrahub/ui and we can delete the app copy.
export const focusVisibleStyle = cn(
  "transition-all data-focus-visible:border-ring data-focus-visible:outline-hidden data-focus-visible:ring-2 data-focus-visible:ring-ring-halo"
);
