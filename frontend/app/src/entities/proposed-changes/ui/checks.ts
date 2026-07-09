import { VALIDATION_CONCLUSIONS, VALIDATION_STATES } from "@/entities/diff/domain/model/check";
import { CHECKS_LABEL } from "@/entities/diff/ui/checks/checks-labels";

export const getValidatorsStats = (validators: any[]) => {
  const successValidators = validators.filter(
    (validator: any) =>
      validator.state.value === VALIDATION_STATES.COMPLETED &&
      validator.conclusion.value === VALIDATION_CONCLUSIONS.SUCCESS
  );

  const inProgressValidators = validators.filter(
    (validator: any) => validator.state.value === VALIDATION_STATES.IN_PROGRESS
  );

  const failedValidators = validators.filter(
    (validator: any) =>
      validator.state.value === VALIDATION_STATES.COMPLETED &&
      validator.conclusion.value === VALIDATION_CONCLUSIONS.FAILURE
  );

  const unknownValidators = validators.filter(
    (validator: any) =>
      validator.state.value === VALIDATION_STATES.COMPLETED &&
      validator.conclusion.value === VALIDATION_CONCLUSIONS.UNKNOWN
  );

  const queuedValidators = validators.filter(
    (validator: any) => validator.state.value === VALIDATION_STATES.QUEUED
  );

  if (!successValidators.length && !inProgressValidators.length && !failedValidators.length) {
    return [
      {
        name: CHECKS_LABEL.EMPTY,
        value: 1,
      },
    ];
  }

  return [
    successValidators.length && {
      name: CHECKS_LABEL.SUCCESS,
      value: successValidators.length,
      className: "fill-green-400",
    },
    inProgressValidators.length && {
      name: CHECKS_LABEL.IN_PROGRESS,
      value: inProgressValidators.length,
      className: "fill-orange-400",
    },
    failedValidators.length && {
      name: CHECKS_LABEL.FAILURE,
      value: failedValidators.length,
      className: "fill-red-400",
    },
    queuedValidators.length && {
      name: CHECKS_LABEL.QUEUED,
      value: queuedValidators.length,
      className: "fill-yellow-300",
    },
    unknownValidators.length && {
      name: CHECKS_LABEL.UNKNOWN,
      value: unknownValidators.length,
      className: "fill-gray-400",
    },
  ].filter(Boolean);
};
