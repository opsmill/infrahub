import React from "react";

interface StackContextValue {
  onChildOpen: () => void;
  onChildClose: () => void;
}

const StackContext = React.createContext<StackContextValue>({
  onChildOpen: () => {},
  onChildClose: () => {},
});

interface StackedProps {
  isStacked?: boolean;
  children: (stackOffset: number) => React.ReactNode;
}

export function Stacked({ isStacked, children }: StackedProps) {
  const parent = React.use(StackContext);
  const [layersAbove, setLayersAbove] = React.useState(0);

  React.useLayoutEffect(() => {
    if (!isStacked) return;
    parent.onChildOpen();
    return () => parent.onChildClose();
  }, [isStacked]);

  const onChildOpen = () => {
    setLayersAbove((c) => c + 1);
    parent.onChildOpen();
  };
  const onChildClose = () => {
    setLayersAbove((c) => c - 1);
    parent.onChildClose();
  };

  return <StackContext value={{ onChildOpen, onChildClose }}>{children(layersAbove)}</StackContext>;
}
