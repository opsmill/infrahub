import { RouterProvider as AriaRouterProvider } from "react-aria-components";
import { type NavigateOptions, type To, useHref, useNavigate } from "react-router";

declare module "react-aria-components" {
  interface RouterConfig {
    href: To;
    routerOptions: NavigateOptions;
  }
}

const EXTERNAL_HREF_PREFIXES = ["https://", "http://", "mailto:", "blob:", "data:"];

function useAbsoluteHref(path: To) {
  const relative = useHref(path);
  if (typeof path === "string" && EXTERNAL_HREF_PREFIXES.some((prefix) => path.startsWith(prefix))) {
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
