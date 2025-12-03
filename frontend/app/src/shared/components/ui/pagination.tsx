import ReactPaginate from "react-paginate";

import usePagination from "@/shared/hooks/usePagination";
import { classNames } from "@/shared/utils/common";

import { Combobox, ComboboxContent, ComboboxItem, ComboboxTrigger } from "./combobox";
import { Command, CommandList } from "./command";

type tPaginationType = {
  count?: number;
  className?: string;
};

export const Pagination = (props: tPaginationType) => {
  const { count = 0, className } = props;

  const [pagination, setPagination] = usePagination();

  const { offset, limit } = pagination;

  // Set the number of page to 1 if there is no other pages
  const pagesCount = Math.ceil(count / limit) || 1;

  // Set the current page to 0 as it is an index
  const currentPage = offset / limit;

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

  const handleLimitChange = (newLimit: number) => {
    if (newLimit === limit) {
      return;
    }

    const newPagination = {
      limit: newLimit,
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
    <div
      className={classNames(
        "sticky bottom-0 flex items-center justify-between bg-white p-2 dark:bg-slate-700",
        className
      )}
    >
      <div className="flex flex-1 flex-wrap justify-between gap-2">
        <div className="flex items-center gap-4">
          <div className="text-gray-700 text-sm dark:text-gray-300">{paginationText}</div>

          <div>
            <Combobox>
              <ComboboxTrigger data-testid="pagination-size-select">{limit}</ComboboxTrigger>

              <ComboboxContent fitTriggerWidth={false}>
                <Command>
                  <CommandList>
                    {[10, 20, 50].map((option) => {
                      const optionAsString = option.toString();
                      const currentLimitAsString = limit.toString();

                      return (
                        <ComboboxItem
                          key={option}
                          value={optionAsString}
                          selectedValue={currentLimitAsString}
                          onSelect={() => {
                            handleLimitChange(option);
                          }}
                        >
                          {optionAsString}
                        </ComboboxItem>
                      );
                    })}
                  </CommandList>
                </Command>
              </ComboboxContent>
            </Combobox>
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
            pageClassName="cursor-pointer relative inline-flex items-center border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-slate-500 dark:text-gray-300 dark:hover:bg-slate-600"
            pageLinkClassName="cursor-pointer px-4 py-2"
            previousClassName="cursor-pointer relative inline-flex items-center rounded-l-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-slate-500 dark:text-gray-300 dark:hover:bg-slate-600"
            previousLinkClassName="cursor-pointer px-4 py-2"
            nextLabel="Next"
            nextClassName="cursor-pointer relative inline-flex items-center rounded-r-md border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-slate-500 dark:text-gray-300 dark:hover:bg-slate-600"
            nextLinkClassName="cursor-pointer px-4 py-2"
            breakLabel="..."
            breakClassName="cursor-pointer relative inline-flex items-center text-sm font-semibold text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 dark:text-gray-300 dark:ring-slate-500 dark:hover:bg-slate-600"
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
