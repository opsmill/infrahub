import React from "react";

interface StackContextValue {
<<<<<<< HEAD
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
=======
  onChildOpen: () => void;
  onChildClose: () => void;
}

const noop = () => {
  // Intentionally empty: default no-op for unstacked roots.
};

const INITIAL_LAYERS = 0;
const LAYER_DELTA = 1;

const DEFAULT_STACK_CONTEXT: StackContextValue = {
  onChildOpen: noop,
  onChildClose: noop,
};

const StackContext = React.createContext<StackContextValue>(DEFAULT_STACK_CONTEXT);

interface StackedProps {
  isStacked?: boolean;
  children: (stackOffset: number) => React.ReactNode;
}

export function Stacked({ isStacked, children }: StackedProps) {
  const parent = React.use(StackContext);
  const [layersAbove, setLayersAbove] = React.useState(INITIAL_LAYERS);
>>>>>>> origin/stable

  React.useLayoutEffect(() => {
    if (!isStacked) {
      return;
    }
<<<<<<< HEAD
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
=======
    parent.onChildOpen();
    return () => parent.onChildClose();
    // oxlint-disable-next-line react/exhaustive-deps -- parent identity intentionally not tracked; effect should fire only on isStacked changes
  }, [isStacked]);

  const onChildOpen = () => {
    setLayersAbove((current) => current + LAYER_DELTA);
    parent.onChildOpen();
  };
  const onChildClose = () => {
    setLayersAbove((current) => current - LAYER_DELTA);
    parent.onChildClose();
  };

  const value: StackContextValue = { onChildOpen, onChildClose };

  // oxlint-disable-next-line react/jsx-no-constructed-context-values -- React Compiler memoizes this value
  return <StackContext value={value}>{children(layersAbove)}</StackContext>;
>>>>>>> origin/stable
}
