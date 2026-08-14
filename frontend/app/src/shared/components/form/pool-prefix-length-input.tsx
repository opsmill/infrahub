import { Row } from "@/shared/components/container";
import { focusWithinStyle, inputErrorStyle, inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import {
  MAX_PREFIX_LENGTH,
  MIN_PREFIX_LENGTH,
} from "@/entities/resource-manager/domain/model/pool";

export interface PoolPrefixLengthInputProps {
  value: number | null | undefined;
  invalid?: boolean;
  /** Pool's default prefix length, shown as a hint of the mask used when left blank. */
  placeholder?: string;
  onChange: (value: number | null) => void;
}

/**
 * Compact inline editor for a from-pool allocation's prefix-length override. The pool field
 * decides when it is shown and validates the value (integer, 1-128); this just edits it.
 * Clearing emits `null` so react-hook-form writes the empty state.
 */
export function PoolPrefixLengthInput({
  value,
  invalid,
  placeholder,
  onChange,
}: PoolPrefixLengthInputProps) {
  return (
    <Row
      className={classNames(inputStyle, focusWithinStyle, "w-18 gap-1", invalid && inputErrorStyle)}
      title="Prefix length"
    >
      <span className="text-subtle-muted">/</span>
      <input
        type="number"
        min={MIN_PREFIX_LENGTH}
        max={MAX_PREFIX_LENGTH}
        value={value ?? ""}
        onChange={(event) => {
          // type="number" yields NaN for an empty or intermediate-invalid value; treat as cleared.
          const next = event.target.valueAsNumber;
          onChange(Number.isNaN(next) ? null : next);
        }}
        placeholder={placeholder}
        aria-label="Prefix length"
        data-testid="pool-prefix-length-input"
        className="w-full min-w-0 appearance-none border-0 bg-transparent p-0 outline-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      />
    </Row>
  );
}
