import { StringParam, useQueryParam } from "use-query-params";

import { QSP } from "@/config/qsp";

type tPagination = {
  limit: number;
  offset: number;
};

const DEFAULT_OFFSET = 0;
const DEFAULT_LIMIT = 10;
const AVAILABLE_LIMITS = [10, 20, 50];

const getVerifiedLimit = (limit: number, config: any) => {
  const availableLimits = config?.availableLimits ?? AVAILABLE_LIMITS;
  const defaultLimit = config?.defaultLimit ?? DEFAULT_LIMIT;

  if (!availableLimits.includes(limit)) {
    return defaultLimit;
  }

  return limit;
};

const getVerifiedOffset = (offset: number, config: any) => {
  const defaultOffset = config?.defaultOffset ?? DEFAULT_OFFSET;

  if (isNaN(offset)) {
    return defaultOffset;
  }

  return offset;
};

const usePagination = (): [tPagination, Function] => {
  const [paginationInQueryString, setPaginationInQueryString] = useQueryParam(
    QSP.PAGINATION,
    StringParam
  );

  const parsedPagination = paginationInQueryString
    ? JSON.parse(paginationInQueryString ?? "{}")
    : {};

  // Get the final pagination with verifyed values
  const pagination = {
    limit: getVerifiedLimit(parsedPagination?.limit, null),
    offset: getVerifiedOffset(parsedPagination?.offset, null),
  };

  // Set the pagination in the QSP
  const setPagination = (newPagination: tPagination) => {
    const newLimit = getVerifiedLimit(newPagination?.limit, null);
    const newOffset = getVerifiedOffset(newPagination?.offset, null);

    const newValidatedPagination = {
      limit: newLimit,
      offset: newOffset,
    };

    setPaginationInQueryString(JSON.stringify(newValidatedPagination));
  };

  return [pagination, setPagination];
};

export default usePagination;
