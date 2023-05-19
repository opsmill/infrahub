import { Cog6ToothIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import * as R from "ramda";
import { useState } from "react";
import { getRandomUser, iUser } from "../../data/users";

const getRandomUserList = (): { [k: string]: iUser[] } => {
  let list: iUser[] = [];
  for (let i = 0; i < 50; i++) {
    const user = getRandomUser();
    if (!user) {
      continue;
    }
    user.avatar_url =
      user.gender === "Male"
        ? `https://randomuser.me/api/portraits/men/${user.id}.jpg`
        : `https://randomuser.me/api/portraits/women/${user.id}.jpg`;

    list.push(user);
  }

  const sortByFirstName = R.sortBy(R.compose(R.prop("first_name")));
  list = sortByFirstName(list);
  let directory: { [k: string]: iUser[] } = {};
  list.forEach((user) => {
    const initial = user.first_name[0].toUpperCase();
    if (directory[initial]) {
      directory[initial].push(user);
    } else {
      directory[initial] = [user];
    }
  });
  return directory;
};

export default function UserItems() {
  const [users] = useState<{ [k: string]: iUser[] }>(getRandomUserList());
  const [selected, setSelected] = useState<iUser>();
  return (
    <>
      {/* <div className="border-b border-gray-200 p-4 sm:flex sm:items-center sm:justify-between bg-white">
        <h3 className="text-base font-semibold leading-6 text-gray-900">Users</h3>
        <div className="mt-3 sm:ml-4 sm:mt-0">
          <button
            type="button"
            className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
          >
                Create new user
          </button>
        </div>
      </div> */}
      <div className="flex overflow-auto bg-white">
        <div className="flex flex-col">
          <div className="p-2">
            <div className="relative rounded-md shadow-sm">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
              </div>
              <input
                type="text"
                name="search"
                id="search"
                className="block w-full rounded-md border-0 py-1.5 pl-10 text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                placeholder="Search"
              />
            </div>
          </div>
          <nav className="h-full overflow-y-auto" aria-label="Directory">
            {Object.keys(users).map((letter: string) => {
              return (
                <div key={letter} className="relative">
                  <div className="sticky top-0 z-10 border-y border-b-gray-200 border-t-gray-100 bg-gray-50 px-4 py-1.5 text-sm font-semibold leading-6 text-gray-900">
                    <h3>{letter}</h3>
                  </div>
                  <ul className="divide-y divide-gray-100">
                    {users[letter].map((person: iUser) => (
                      <li
                        key={person.email}
                        className="flex gap-x-4 px-4 py-4 cursor-pointer hover:bg-gray-100"
                        onClick={() => setSelected(person)}>
                        <img
                          className="h-12 w-12 flex-none rounded-full bg-gray-50"
                          src={person.avatar_url}
                          alt=""
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold leading-6 text-gray-900">
                            {person.first_name} {person.last_name}
                          </p>
                          <p className="truncate text-xs leading-5 text-gray-500">{person.email}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </nav>
        </div>
        <div className="flex-1 flex flex-col border-l">
          {selected && (
            <div className="flex p-4 border-b items-center">
              <img
                className="h-10 w-10 flex-none rounded-full bg-gray-50"
                src={selected.avatar_url}
                alt=""
              />
              <div className="min-w-0 pl-2 flex-1">
                <div className="text-sm font-semibold text-gray-900">
                  {selected.first_name} {selected.last_name}
                </div>
                <div className="truncate text-xs leading-5 text-gray-500">{selected.email}</div>
              </div>
              <Cog6ToothIcon className="w-6 h-6 text-gray-600 cursor-pointer" />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
