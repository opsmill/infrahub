import {
  CHECKS_LABEL,
  CHECK_CONCLUSIONS,
  CHECK_SEVERITY,
  VALIDATION_CONCLUSIONS,
  VALIDATION_STATES,
} from "../config/constants";

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

  const unkownValidators = validators.filter(
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
    {
      name: CHECKS_LABEL.SUCCESS,
      value: successValidators.length,
      className: "fill-green-400",
    },
    {
      name: CHECKS_LABEL.IN_PROGRESS,
      value: inProgressValidators.length,
      className: "fill-orange-400",
    },
    {
      name: CHECKS_LABEL.FAILURE,
      value: failedValidators.length,
      className: "fill-red-400",
    },
    {
      name: CHECKS_LABEL.QUEUED,
      value: queuedValidators.length,
      className: "fill-yellow-300",
    },
    {
      name: CHECKS_LABEL.UNKOWN,
      value: unkownValidators.length,
      className: "fill-gray-400",
    },
  ];
};

export const getChecksStats = (checks: any[]) => {
  const inProgressChecks = checks.filter(
    (validator: any) => validator.conclusion.value === CHECK_CONCLUSIONS.UNKNOWN
  );

  const successChecks = checks.filter(
    (validator: any) =>
      validator.severity.value === CHECK_SEVERITY.SUCCESS &&
      validator.conclusion.value === CHECK_CONCLUSIONS.SUCCESS
  );

  const infoChecks = checks.filter(
    (validator: any) =>
      validator.severity.value === CHECK_SEVERITY.INFO &&
      validator.conclusion.value === CHECK_CONCLUSIONS.SUCCESS
  );

  const warningChecks = checks.filter(
    (validator: any) =>
      validator.severity.value === CHECK_SEVERITY.WARNING &&
      validator.conclusion.value === CHECK_CONCLUSIONS.FAILURE
  );

  const errorChecks = checks.filter(
    (validator: any) =>
      validator.severity.value === CHECK_SEVERITY.ERROR &&
      validator.conclusion.value === CHECK_CONCLUSIONS.FAILURE
  );

  const criticalChecks = checks.filter(
    (validator: any) =>
      validator.severity.value === CHECK_SEVERITY.CRITICAL &&
      validator.conclusion.value === CHECK_CONCLUSIONS.FAILURE
  );

  return {
    total: checks.length,
    success: successChecks.length,
    info: infoChecks.length,
    warning: warningChecks.length,
    error: errorChecks.length,
    critical: criticalChecks.length,
    inProgress: inProgressChecks.length,
  };
};
