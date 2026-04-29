import React from "react";

interface StackContextValue {
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

  React.useLayoutEffect(() => {
    if (!isStacked) {
      return;
    }
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
}
