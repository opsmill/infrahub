import { Button, type ButtonProps, Card } from "@infrahub/ui";
import { PanelLeftCloseIcon, PanelLeftOpenIcon } from "lucide-react";
import * as React from "react";

import { useLocalStorage } from "@/shared/hooks/useLocalStorage";
import { classNames } from "@/shared/utils/common";

import { SIDEBAR_STATE_KEY } from "@/entities/navigation/constants";

type SidebarContextProps = {
  isCollapsed: boolean;
  toggleSidebar: () => void;
};

const SidebarContext = React.createContext<SidebarContextProps | null>(null);

export function useSidebar() {
  const context = React.useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider.");
  }

  return context;
}

export function SidebarProvider({ children }: { children?: React.ReactNode }) {
  const [storedState, setStoredState] = useLocalStorage(SIDEBAR_STATE_KEY);

  // Default to expanded; only the explicit "collapsed" string collapses the sidebar.
  // Storing the literal state (not a boolean) keeps localStorage self-describing and
  // removes the "is collapsed" vs "is open" inversion bug class.
  const isCollapsed = storedState === "collapsed";

  return (
    <SidebarContext.Provider
      value={{
        isCollapsed,
        toggleSidebar: () => setStoredState(isCollapsed ? "expanded" : "collapsed"),
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
}

export function Sidebar({ className, children, ...props }: React.ComponentProps<"div">) {
  const { isCollapsed } = useSidebar();

  return (
    <Card
      className={classNames(
        "group w-64 shrink-0 overflow-hidden transition-[width] duration-200 ease-linear data-[state=collapsed]:w-14",
        className
      )}
      data-state={isCollapsed ? "collapsed" : "expanded"}
      {...props}
    >
      {children}
    </Card>
  );
}

export function SidebarTrigger({ className, onPress, ...props }: ButtonProps) {
  const { isCollapsed, toggleSidebar } = useSidebar();

  return (
    <Button
      variant="ghost"
      shape="square"
      size="sm"
      className={classNames("text-gray-400 data-hovered:text-neutral-600", className)}
      onPress={(event) => {
        onPress?.(event);
        toggleSidebar();
      }}
      {...props}
    >
      {isCollapsed ? (
        <PanelLeftOpenIcon className="size-5" />
      ) : (
        <PanelLeftCloseIcon className="size-5" />
      )}
      <span className="sr-only">Toggle Sidebar</span>
    </Button>
  );
}

export function SidebarHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={classNames("flex flex-col gap-2 p-2", className)} {...props} />;
}

export function SidebarContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={classNames(
        "no-scrollbar flex min-h-0 flex-1 flex-col gap-0 overflow-hidden",
        className
      )}
      {...props}
    />
  );
}

export function SidebarFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={classNames("flex flex-col gap-2 p-2", className)} {...props} />;
}
