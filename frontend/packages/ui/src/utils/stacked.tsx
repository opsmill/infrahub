import React from "react";

interface StackContextValue {
  onChildOpen: (stackGroup: string) => void;
  onChildClose: (stackGroup: string) => void;
}

const StackContext = React.createContext<StackContextValue>({
  onChildOpen: () => {},
  onChildClose: () => {},
});

interface StackedProps {
  group: string;
  isStacked?: boolean;
  children: (depth: number) => React.ReactNode;
}

export function Stacked({ group, isStacked, children }: StackedProps) {
  const parent = React.use(StackContext);
  const [layersAbove, setLayersAbove] = React.useState(0);

  React.useLayoutEffect(() => {
    if (!isStacked) return;
    parent.onChildOpen(group);
    return () => parent.onChildClose(group);
  }, [isStacked, group]);

  const onChildOpen = (childGroup: string) => {
    if (childGroup === group) setLayersAbove((c) => c + 1);
    parent.onChildOpen(childGroup);
  };
  const onChildClose = (childGroup: string) => {
    if (childGroup === group) setLayersAbove((c) => c - 1);
    parent.onChildClose(childGroup);
  };

  return <StackContext value={{ onChildOpen, onChildClose }}>{children(layersAbove)}</StackContext>;
}
