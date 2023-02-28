export default function NoDataFound() {
    return (
      <div className="p-12 flex flex-col flex-1 items-center justify-center">
        <img className="h-28 w-auto" src="https://thesuccessfinder.com/images/data-not-found-icon.png" />
        <div className="pt-2">Sorry, no data found.</div>
      </div>
    )
  }