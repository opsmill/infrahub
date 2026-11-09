import React from "react";

interface StackContextValue {
  onChildOpen: (stackGroup: string) => void;
  onChildClose: (stackGroup: string) => void;
  layersBelow: (stackGroup: string) => number;
}

const StackContext = React.createContext<StackContextValue>({
  onChildOpen: () => {},
  onChildClose: () => {},
  layersBelow: () => 0,
});

interface StackedRenderProps {
  depth: number;
  totalCount: number;
}

interface StackedProps {
  group: string;
  isStacked?: boolean;
  children: (props: StackedRenderProps) => React.ReactNode;
}

export function Stacked({ group, isStacked, children }: StackedProps) {
  const parent = React.use(StackContext);
  const [layersAbove, setLayersAbove] = React.useState(0);

  React.useLayoutEffect(() => {
    if (!isStacked) {
      return;
    }
    parent.onChildOpen(group);
    return () => parent.onChildClose(group);
  }, [isStacked, group, parent]);

  const onChildOpen = (childGroup: string) => {
    if (childGroup === group) {
      setLayersAbove((c) => c + 1);
    }
    parent.onChildOpen(childGroup);
  };
  const onChildClose = (childGroup: string) => {
    if (childGroup === group) {
      setLayersAbove((c) => c - 1);
    }
    parent.onChildClose(childGroup);
  };

  const layersBelow = parent.layersBelow(group) + (isStacked ? 1 : 0);
  const depth = layersAbove;
  const totalCount = layersBelow + layersAbove;

  const value: StackContextValue = {
    onChildOpen,
    onChildClose,
    layersBelow: (childGroup) =>
      childGroup === group ? layersBelow : parent.layersBelow(childGroup),
  };

  return <StackContext value={value}>{children({ depth, totalCount })}</StackContext>;
}
