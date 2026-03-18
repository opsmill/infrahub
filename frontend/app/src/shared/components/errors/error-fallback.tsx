import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";

import Accordion from "@/shared/components/display/accordion";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import Kbd from "@/shared/components/ui/kbd";

interface ErrorFallbackProps {
  error: Error;
  onReset: () => void;
}

function ErrorFallback({ error, onReset }: ErrorFallbackProps) {
  const [bugPosition, setBugPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "enter") {
        onReset();
      }

      if (event.key.toLowerCase() === "backspace") {
        window.location.href = window.location.origin;
      }
    };

    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
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
    <div className="flex h-screen flex-col items-center justify-center bg-gray-100">
      <Card className="mb-4 flex flex-col items-center p-4">
        <h1 className="font-semibold text-lg">Uh-oh, something went wrong :(</h1>

        <div>
          <p className="flex items-center gap-1">
            You might have encounter a{" "}
            <Icon
              icon="mdi:bug"
              className="relative cursor-pointer text-custom-blue-600 text-xl transition-all"
              style={bugPosition}
              onMouseEnter={handleMoveOnBug}
              onClick={handleMoveOnBug}
            />
            ...
          </p>

          <div>
            <Button className="mr-2" onClick={onReset}>
              Refresh
            </Button>
            <a href={window.location.origin}>
              <Button variant="outline" className="my-4">
                Homepage
              </Button>
            </a>
          </div>

          <p className="mb-1 font-medium text-xs">
            Press{" "}
            <Kbd keys={["enter"]} keyClassName="relative top-px mr-1">
              enter
            </Kbd>{" "}
            to try again
          </p>
          <p className="mb-4 font-medium text-xs">
            Press{" "}
            <Kbd keys={["delete"]} keyClassName="mr-1">
              backspace
            </Kbd>{" "}
            to go back to Homepage
          </p>
        </div>
        <p className="text-gray-600 text-xs">
          If this was unexpected, please reach out to us on{" "}
          <a
            className="underline"
            href="https://discord.gg/opsmill"
            target="_blank"
            rel="noreferrer"
          >
            Discord
          </a>
          {" or "}
          <a
            className="underline"
            href="https://github.com/opsmill/infrahub/issues/new/choose"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
        </p>
      </Card>

      {error?.stack && (
        <Accordion className="text-gray-600 text-sm" title="View error stack">
          <pre className="rounded-sm bg-red-50 p-2 text-red-800">{error.stack}</pre>
        </Accordion>
      )}
    </div>
  );
}

export default ErrorFallback;
