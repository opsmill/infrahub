import { Checkbox } from "@infrahub/ui";
import { useAtom, useAtomValue } from "jotai";
import { ZapIcon, ZapOffIcon } from "lucide-react";
import React from "react";

import { Col } from "@/shared/components/container";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import { Badge } from "@/shared/components/ui/badge";
import { Input } from "@/shared/components/ui/input";
import Label from "@/shared/components/ui/label";
import {
  type ParallelQueryConfig,
  parallelQueryConfigAtom,
} from "@/shared/libs/graphiql/parallel-query-mode";

interface NumberSettingProps extends React.ComponentProps<"input"> {
  label: string;
  description: string;
  value: number;
}

function NumberSetting({ label, description, value, ...inputProps }: NumberSettingProps) {
  const id = React.useId();
  const inputRef = usePreventScrollOnNumberInput();

  return (
    <Col className="gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Input
        ref={inputRef}
        id={id}
        type="number"
        value={Number.isNaN(value) ? "" : value}
        {...inputProps}
      />
      <p className="text-foreground-muted text-xs">{description}</p>
    </Col>
  );
}

function ParallelModePlugin() {
  const [config, setConfig] = useAtom(parallelQueryConfigAtom);

  // Local state for input values to allow empty fields during editing
  const [pageSize, setPageSize] = React.useState(config.pageSize);
  const [maxConcurrent, setMaxConcurrent] = React.useState(config.maxConcurrent);
  const [delayMs, setDelayMs] = React.useState(config.delayMs);

  React.useEffect(() => {
    setPageSize(config.pageSize);
    setMaxConcurrent(config.maxConcurrent);
    setDelayMs(config.delayMs);
  }, [config.pageSize, config.maxConcurrent, config.delayMs]);

  const updateConfig = (partial: Partial<ParallelQueryConfig>) => {
    setConfig((current) => ({ ...current, ...partial }));
  };

  const toggleEnabled = () => {
    updateConfig({ enabled: !config.enabled });
  };

  return (
    <div className="h-full overflow-y-auto p-4">
      <Badge variant="warning">Alpha</Badge>
      <div className="mb-4 flex items-center gap-2 font-semibold text-lg">
        Parallel Mode Settings
      </div>
      <p className="mb-4 text-foreground-muted text-sm">
        When enabled, queries without <code>offset</code> or <code>limit</code> arguments will be
        automatically paginated and executed in parallel for better performance on large datasets.
      </p>

      <div className="mb-6 space-y-4">
        <Checkbox isSelected={config.enabled} onChange={toggleEnabled}>
          Enable Parallel Mode
        </Checkbox>

        {config.enabled && (
          <div className="space-y-4 border-l-2 pl-4">
            <NumberSetting
              label="Page Size"
              description="Number of items per page (default: 500)"
              value={pageSize}
              onChange={(e) => setPageSize(e.target.valueAsNumber)}
              onBlur={() => {
                if (!pageSize || pageSize < 1) {
                  updateConfig({ pageSize: 500 });
                  setPageSize(500);
                } else if (pageSize > 10_000) {
                  updateConfig({ pageSize: 10_000 });
                  setPageSize(10_000);
                } else {
                  updateConfig({ pageSize });
                }
              }}
              min={1}
              max={10_000}
            />

            <NumberSetting
              label="Max Concurrent Requests"
              description="Maximum parallel requests (default: 5, max: 50)"
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(e.target.valueAsNumber)}
              onBlur={() => {
                if (!maxConcurrent || maxConcurrent < 1) {
                  updateConfig({ maxConcurrent: 5 });
                  setMaxConcurrent(5);
                } else if (maxConcurrent > 50) {
                  updateConfig({ maxConcurrent: 50 });
                  setMaxConcurrent(50);
                } else {
                  updateConfig({ maxConcurrent });
                }
              }}
              min={1}
              max={50}
            />

            <NumberSetting
              label="Delay Between Queries (ms)"
              description="Delay between each query in milliseconds (default: disabled)"
              value={delayMs}
              onChange={(e) => setDelayMs(e.target.valueAsNumber)}
              onBlur={() => {
                if (delayMs < 0 || Number.isNaN(delayMs)) {
                  updateConfig({ delayMs: 0 });
                  setDelayMs(0);
                } else if (delayMs > 5000) {
                  updateConfig({ delayMs: 5000 });
                  setDelayMs(5000);
                } else {
                  updateConfig({ delayMs });
                }
              }}
              min={0}
              max={5000}
            />
          </div>
        )}
      </div>

      <div className="border-t pt-4">
        <div className="font-medium text-sm text-subtle">How it works:</div>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-foreground-muted text-xs">
          <li>Executes a count query to determine total items</li>
          <li>Splits into multiple paginated queries</li>
          <li>Executes queries in parallel batches</li>
          <li>Merges results into a single response</li>
        </ol>
      </div>
    </div>
  );
}

function ParallelModeIcon(props: React.ComponentProps<typeof ZapIcon>) {
  const { enabled } = useAtomValue(parallelQueryConfigAtom);

  if (enabled) return <ZapIcon {...props} />;
  return <ZapOffIcon {...props} />;
}

export const parallelModePlugin = {
  title: "Parallel Mode",
  icon: ParallelModeIcon,
  content: ParallelModePlugin,
};
