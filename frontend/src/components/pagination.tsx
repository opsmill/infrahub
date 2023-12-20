import ReactPaginate from "react-paginate";
import usePagination from "../hooks/usePagination";
import { Select, SelectDirection, SelectOption } from "./select";

type tPaginationType = {
  count?: number;
};

const limitOptions: SelectOption[] = [
  {
    id: 10,
    name: "10",
  },
  {
    id: 20,
    name: "20",
  },
  {
    id: 50,
    name: "50",
  },
];

export const Pagination = (props: tPaginationType) => {
  const { count = 0 } = props;

  const [pagination, setPagination] = usePagination();

  const { offset, limit } = pagination;

  // Set the number of page to 1 if there is no other pages
  const pagesCount = Math.ceil(count / limit) || 1;

  // Set the current page to 0 as it is an index
  const currentPage = offset / limit ?? 0;

  const offsetEnd = offset + limit > count ? count : offset + limit;
  const offsetStart = offsetEnd > 0 ? offset + 1 : 0;

  const handlePageChange = (page: any) => {
    const { nextSelectedPage } = page;

    const newOffset = nextSelectedPage * limit || 0;

    if (newOffset === offset) {
      return;
    }

    const newPagination = {
      limit,
      offset: newOffset,
    };

    setPagination(newPagination);
  };

  const handleLimitChange = (option: SelectOption) => {
    if (option.id === limit) {
      return;
    }

    const newPagination = {
      limit: option.id,
      offset,
    };

    setPagination(newPagination);
  };

  const paginationText =
    offsetStart !== offsetEnd ? (
      <>
        Showing <span className="font-medium">{offsetStart}</span> to{" "}
        <span className="font-medium">{offsetEnd}</span> of{" "}
        <span className="font-medium">{count}</span> results
      </>
    ) : (
      <>
        Showing <span className="font-medium">{offsetStart}</span> of{" "}
        <span className="font-medium">{count}</span> results
      </>
    );

  return (
    <div className="sticky bottom-0 flex items-center justify-between border-t border-gray-200 bg-custom-white p-2">
      <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
        <div className="flex items-center">
          <div className="text-sm text-gray-700">{paginationText}</div>

          <div className="w-[75px] ml-8">
            <Select
              options={limitOptions}
              value={limit}
              onChange={handleLimitChange}
              direction={SelectDirection.OVER}
              preventEmpty
            />
          </div>
        </div>
        <div>
          <ReactPaginate
            initialPage={currentPage}
            onClick={handlePageChange}
            pageRangeDisplayed={3}
            marginPagesDisplayed={2}
            pageCount={pagesCount}
            previousLabel="Previous"
            pageClassName="cursor-pointer relative inline-flex items-center border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            pageLinkClassName="cursor-pointer px-4 py-2"
            previousClassName="cursor-pointer relative inline-flex items-center rounded-l-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            previousLinkClassName="cursor-pointer px-4 py-2"
            nextLabel="Next"
            nextClassName="cursor-pointer relative inline-flex items-center rounded-r-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            nextLinkClassName="cursor-pointer px-4 py-2"
            breakLabel="..."
            breakClassName="cursor-pointer relative inline-flex items-center text-sm font-semibold text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0"
            breakLinkClassName="cursor-pointer px-4 py-2"
            containerClassName="flex"
            activeClassName="bg-custom-blue-100 text-custom-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-custom-blue-100 hover:bg-custom-blue-100"
            activeLinkClassName="cursor-pointer px-4 py-2 text-custom-white"
          />
        </div>
      </div>
    </div>
  );
};
