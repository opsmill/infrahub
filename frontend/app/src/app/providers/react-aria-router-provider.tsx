import { RouterProvider as AriaRouterProvider } from "react-aria-components";
import { type NavigateOptions, type To, useHref, useNavigate } from "react-router";

declare module "react-aria-components" {
  interface RouterConfig {
    href: To;
    routerOptions: NavigateOptions;
  }
}

const EXTERNAL_HREF_PREFIXES = ["https://", "http://", "mailto:", "blob:", "data:"];

function isExternalHref(path: To): path is string {
  return (
    typeof path === "string" && EXTERNAL_HREF_PREFIXES.some((prefix) => path.startsWith(prefix))
  );
}

function useAbsoluteHref(path: To) {
  const relative = useHref(path);
  return isExternalHref(path) ? path : relative;
}

export function ReactAriaRouterProvider({ children }: { children: React.ReactNode }) {
  const routerNavigate = useNavigate();

  // A same-origin link is handed to this function even when its absolute URL has no client-side route.
  const navigate = (to: To, options?: NavigateOptions) => {
    if (isExternalHref(to)) {
      window.location.assign(to);
      return;
    }
    routerNavigate(to, options);
  };

  return (
    <AriaRouterProvider navigate={navigate} useHref={useAbsoluteHref}>
      {children}
    </AriaRouterProvider>
  );
}
