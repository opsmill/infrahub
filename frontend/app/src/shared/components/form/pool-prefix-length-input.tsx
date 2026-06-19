import { Row } from "@/shared/components/container";
import { Input } from "@/shared/components/ui/input";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface PoolPrefixLengthInputProps {
  value: number | null | undefined;
  invalid?: boolean;
  onChange: (value: number | null) => void;
}

/**
 * Compact inline editor for a from-pool allocation's prefix-length override. It is a
 * plain controlled number input; the surrounding pool field decides when it is shown
 * and owns how its value is validated and persisted. Clearing emits `null` (rather
 * than `undefined`) so react-hook-form actually writes the empty state.
 */
export function PoolPrefixLengthInput({ value, invalid, onChange }: PoolPrefixLengthInputProps) {
  const handleChange = (raw: string) => {
    if (raw === "") {
      onChange(null);
      return;
    }
    // Prefix length is integer-only: reject anything that isn't whole digits
    // ("24.5", "1e2", "-1", " 5"). The controlled input reverts the rejected keystroke.
    if (!/^\d+$/.test(raw)) return;
    onChange(Number(raw));
  };

  return (
    <Row
      className={classNames(
        "h-10 w-16 shrink-0 items-center gap-1 rounded-lg border border-neutral-300 px-2",
        invalid && inputErrorStyle
      )}
      title="Prefix length"
    >
      <span className="text-gray-500">/</span>
      <Input
        value={value ?? ""}
        onChange={(event) => handleChange(event.target.value)}
        inputMode="numeric"
        aria-label="Prefix length"
        data-testid="pool-prefix-length-input"
        className="min-h-0 w-full min-w-0 border-0 bg-transparent p-0 focus-visible:ring-0"
      />
    </Row>
  );
}
