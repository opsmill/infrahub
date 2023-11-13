import {
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

  return {
    total: validators.length,
    inProgress: inProgressValidators.length,
    failure: failedValidators.length,
    success: successValidators.length,
  };
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
