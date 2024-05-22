import { useErrorBoundary } from "react-error-boundary";
import React, { useEffect, useState } from "react";
import { Card } from "../../components/ui/card";
import { Icon } from "@iconify-icon/react";
import { Button } from "../../components/buttons/button-primitive";
import Kbd from "../../components/ui/kbd";
import Accordion from "../../components/display/accordion";

type ErrorFallbackProps = {
  error: Error;
};
function ErrorFallback({ error }: ErrorFallbackProps) {
  const { resetBoundary } = useErrorBoundary();
  const [bugPosition, setBugPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const onPressEnterKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "enter") {
        resetBoundary();
      }
    };

    document.addEventListener("keydown", onPressEnterKey);
    return () => document.removeEventListener("keydown", onPressEnterKey);
  }, []);

  const handleMoveOnBug = () => {
    const randomTop = bugPosition.top + Math.floor(Math.random() * 100) - 50;
    const randomLeft = bugPosition.left + Math.floor(Math.random() * 100) - 50;

    setBugPosition({
      top: randomTop,
      left: randomLeft,
    });
  };

  return (
    <div className="bg-gray-100 flex flex-col items-center justify-center h-full">
      <Card className="flex flex-col items-center mb-4 p-4">
        <h1 className="flex items-center gap-2 font-semibold text-lg">
          <Icon
            icon="mdi:bug"
            className="relative text-custom-blue-600 transition-all text-xl cursor-pointer"
            style={bugPosition}
            onMouseEnter={handleMoveOnBug}
            onClick={handleMoveOnBug}
          />
          Uh-oh, something went wrong :(
        </h1>

        <p>Looks like you found a bug...</p>

        <Button className="my-4" onClick={resetBoundary}>
          Refresh
        </Button>

        <p className="font-semibold text-xs mb-1">
          Press <Kbd>Enter</Kbd> to refresh
        </p>
        <p className="text-xs text-gray-600">
          or reach out to us on{" "}
          <a
            className="underline"
            href="https://discord.com/channels/1212332642801025064/1212669187198025759"
            target="_blank"
            rel="noreferrer">
            Discord
          </a>
          {" or "}
          <a
            className="underline"
            href="https://github.com/opsmill/infrahub/issues/new/choose"
            target="_blank"
            rel="noreferrer">
            GitHub
          </a>
          , we will reply super fast.
        </p>
      </Card>

      {error.stack && (
        <Accordion className="text-sm text-gray-600" title="View error stack">
          <pre className="p-2 rounded bg-red-50 text-red-800">{error.stack}</pre>
        </Accordion>
      )}
    </div>
  );
}

export default ErrorFallback;
