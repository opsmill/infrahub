import { parseAsJson, useQueryState } from "nuqs";
import * as z from "zod";

import { QSP } from "@/config/qsp";

const DEFAULT_OFFSET = 0;
const DEFAULT_LIMIT = 10;
const AVAILABLE_LIMITS = [10, 20, 50];

const Pagination = z.object({
  limit: z.number().optional(),
  offset: z.number().optional(),
});
type Pagination = z.infer<typeof Pagination>;

const getVerifiedLimit = (limit: number | undefined) => {
  if (!limit || !AVAILABLE_LIMITS.includes(limit)) {
    return DEFAULT_LIMIT;
  }

  return limit;
};

const getVerifiedOffset = (offset: number | undefined) => {
  if (!offset || isNaN(offset)) {
    return DEFAULT_OFFSET;
  }

  return offset;
};

const usePagination = () => {
  const [parsedPagination, setPaginationInQueryString] = useQueryState(
    QSP.PAGINATION,
    parseAsJson(Pagination).withDefault({ limit: DEFAULT_LIMIT, offset: DEFAULT_OFFSET })
  );
  const pagination = {
    limit: getVerifiedLimit(parsedPagination?.limit),
    offset: getVerifiedOffset(parsedPagination?.offset),
  };

  // Set the pagination in the QSP
  const setPagination = (newPagination: Pagination) => {
    const newLimit = getVerifiedLimit(newPagination?.limit);
    const newOffset = getVerifiedOffset(newPagination?.offset);

    const newValidatedPagination: Pagination = {
      limit: newLimit,
      offset: newOffset,
    };

    setPaginationInQueryString(newValidatedPagination);
  };

  return [pagination, setPagination];
};

export default usePagination;
