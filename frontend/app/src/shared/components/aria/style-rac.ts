// `focusVisibleStyle` is duplicated in frontend/packages/ui/src/styles/focus-visible.ts.
// Keep both copies in sync until the app's aria/* components migrate to @infrahub/ui
// and we can delete the package copy.

export const disabledStyle = "data-disabled:pointer-events-none data-disabled:opacity-50";

export const focusVisibleStyle =
  "transition-all data-focus-visible:outline-hidden data-focus-visible:ring-2 data-focus-visible:ring-custom-blue-600/25 data-focus-visible:border-custom-blue-600";
