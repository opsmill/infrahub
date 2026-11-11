import { RouterProvider as AriaRouterProvider } from "react-aria-components";
import { type NavigateOptions, type To, useHref, useNavigate } from "react-router";

declare module "react-aria-components" {
  interface RouterConfig {
    href: To;
    routerOptions: NavigateOptions;
  }
}

const EXTERNAL_HREF_PREFIXES = ["https://", "http://", "mailto:", "blob:", "data:"];

function hasExternalPrefix(path: string) {
  return EXTERNAL_HREF_PREFIXES.some((prefix) => path.startsWith(prefix));
}

function useAbsoluteHref(path: To) {
  const relative = useHref(path);
  return typeof path === "string" && hasExternalPrefix(path) ? path : relative;
}

function loadPageInBrowser(url: string) {
  window.location.assign(url);
}

interface ReactAriaRouterProviderProps {
  children: React.ReactNode;
  /** Replaces the full-page load, which a browser test cannot stub on `window.location`. */
  loadPage?: (url: string) => void;
}

export function ReactAriaRouterProvider({
  children,
  loadPage = loadPageInBrowser,
}: ReactAriaRouterProviderProps) {
  const routerNavigate = useNavigate();

  // A same-origin link is handed to this function even when its absolute URL has no client-side route.
  const navigate = (to: To, options?: NavigateOptions) => {
    if (typeof to === "string" && hasExternalPrefix(to)) {
      loadPage(to);
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
