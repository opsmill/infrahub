import { RouterProvider as AriaRouterProvider } from "react-aria-components";
import { type NavigateOptions, type To, useHref, useNavigate } from "react-router";

declare module "react-aria-components" {
  interface RouterConfig {
    href: To;
    routerOptions: NavigateOptions;
  }
}

const ABSOLUTE_HREF_PREFIXES = ["https://", "http://", "mailto:", "blob:", "data:"];

function isAbsoluteHref(path: string) {
  return ABSOLUTE_HREF_PREFIXES.some((prefix) => path.startsWith(prefix));
}

function useAbsoluteHref(path: To) {
  const relative = useHref(path);
  return typeof path === "string" && isAbsoluteHref(path) ? path : relative;
}

function navigateWithBrowser(url: string) {
  window.location.assign(url);
}

interface ReactAriaRouterProviderProps {
  children: React.ReactNode;
  browserNavigate?: (url: string) => void;
}

export function ReactAriaRouterProvider({
  children,
  browserNavigate = navigateWithBrowser,
}: ReactAriaRouterProviderProps) {
  const routerNavigate = useNavigate();

  const navigate = (to: To, options?: NavigateOptions) => {
    if (typeof to === "string" && isAbsoluteHref(to)) {
      browserNavigate(to);
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
