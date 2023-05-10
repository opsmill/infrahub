export const C_JSON1 = {
  menu: {
    id: "file",
    popup: {
      menuitem: [
        {
          value: "New",
          onclick: "CreateNewDoc()",
        },
      ],
    },
  },
};

export const C_JSON1_OUTPUT = `{
    menu: {
        id: "file",
        popup: {
            menuitem: [
                {
                    value: "New",
                    onclick: "CreateNewDoc()"
                }
            ]
        }
    }
}`;

export const C_JSON2 = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

export const C_JSON2_OUTPUT = `[
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday"
]`;

export const C_JSON3 = {
  employee: {
    name: "sonoo",
    salary: 56000,
    married: true,
  },
};

export const C_JSON3_OUTPUT = `{
    employee: {
        name: "sonoo",
        salary: 56000,
        married: true
    }
}`;
