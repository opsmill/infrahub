import DateTimePicker from "react-datepicker";

import { FormField } from "@/shared/components/ui/form";
import { DATE_TIME_FORMAT } from "@/shared/utils/date";

import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";

export interface DateRangePickerFieldsProps {
  condition: FilterCondition;
  afterDefault?: string;
  beforeDefault?: string;
}

export function DateRangePickerFields({
  condition,
  afterDefault,
  beforeDefault,
}: DateRangePickerFieldsProps) {
  const isBetween = condition === FILTER_CONDITION.BETWEEN;
  const showAfter = condition === FILTER_CONDITION.AFTER || isBetween;
  const showBefore = condition === FILTER_CONDITION.BEFORE || isBetween;

  return (
    <div className={isBetween ? "flex flex-row gap-4" : "flex flex-col gap-0"}>
      {showAfter && (
        <FormField
          name="afterDate"
          defaultValue={afterDefault ?? undefined}
          render={({ field }) => (
            <div className="flex flex-col gap-1">
              {isBetween && <span className="text-gray-600 text-xs">After</span>}
              <DateTimePicker
                selected={field.value ? new Date(field.value as string) : null}
                onChange={field.onChange}
                inline
                showTimeSelect
                timeIntervals={1}
                calendarStartDay={1}
                dateFormat={DATE_TIME_FORMAT}
                calendarClassName="flex!"
              />
            </div>
          )}
        />
      )}
      {showBefore && (
        <FormField
          name="beforeDate"
          defaultValue={beforeDefault ?? undefined}
          render={({ field }) => (
            <div className="flex flex-col gap-1">
              {isBetween && <span className="text-gray-600 text-xs">Before</span>}
              <DateTimePicker
                selected={field.value ? new Date(field.value as string) : null}
                onChange={field.onChange}
                inline
                showTimeSelect
                timeIntervals={1}
                calendarStartDay={1}
                dateFormat={DATE_TIME_FORMAT}
                calendarClassName="flex!"
              />
            </div>
          )}
        />
      )}
    </div>
  );
}
