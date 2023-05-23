import ReactPaginate from "react-paginate";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";

type tPaginationType = {
  count?: number;
};

export const Pagination = (props: tPaginationType) => {
  const { count = 0 } = props;

  const [paginationInQueryString, setPagination] = useQueryParam(QSP.PAGINATION, StringParam);

  const pagination = paginationInQueryString ? JSON.parse(paginationInQueryString ?? "{}") : {};

  const { offset = 0, limit = 20 } = pagination;

  const pagesCount = Math.floor(count / limit);

  const currentPage = offset / limit;

  const handlePageChange = ({ selected }: any) => {
    const newPagination = {
      offset: selected * limit,
      limit,
    };

    setPagination(JSON.stringify(newPagination));
  };

  return (
    <div className="sticky bottom-0 flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6">
      <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-gray-700">
            Showing <span className="font-medium">{offset + 1}</span> to{" "}
            <span className="font-medium">{limit}</span> of{" "}
            <span className="font-medium">{count}</span> results
          </p>
        </div>
        <div>
          <ReactPaginate
            initialPage={currentPage}
            onClick={handlePageChange}
            pageRangeDisplayed={3}
            marginPagesDisplayed={2}
            pageCount={pagesCount}
            previousLabel="Previous"
            pageClassName="cursor-pointer relative inline-flex items-center border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            previousClassName="cursor-pointer relative inline-flex items-center rounded-l-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            nextLabel="Next"
            nextClassName="cursor-pointer relative inline-flex items-center rounded-r-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            breakLabel="..."
            breakClassName="cursor-pointer relative inline-flex items-center px-4 py-2 text-sm font-semibold text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0"
            containerClassName="flex"
            activeClassName="bg-blue-500 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 hover:bg-blue-500"
          />
        </div>
      </div>
    </div>
  );
};
