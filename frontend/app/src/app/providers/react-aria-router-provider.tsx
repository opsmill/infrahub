import { RouterProvider as AriaRouterProvider } from "react-aria-components";
import { type NavigateOptions, type To, useHref, useNavigate } from "react-router";

declare module "react-aria-components" {
  interface RouterConfig {
    href: To;
    routerOptions: NavigateOptions;
  }
}

function useAbsoluteHref(path: To) {
  const relative = useHref(path);
  if (
    typeof path === "string" &&
    (path.startsWith("https://") || path.startsWith("http://") || path.startsWith("mailto:"))
  ) {
    return path;
  }
  return relative;
}

export function ReactAriaRouterProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();

  return (
    <AriaRouterProvider navigate={navigate} useHref={useAbsoluteHref}>
      {children}
    </AriaRouterProvider>
  );
}
