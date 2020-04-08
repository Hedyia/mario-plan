const INITIAL_STATE = {
  projects: [
    {
      title: "good to build a tutorial",
      content:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit.Officia, non.",
      createdAt: "3rd septamper, 2am",
    },
    {
      title: "good to experiment with web technologies",
      content:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit.Officia, non.",
      createdAt: "3rd septamper, 2am",
    },
    {
      title: "not something that will take a week to figure out",
      content:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit.Officia, non.",
      createdAt: "3rd septamper, 2am",
    },
    {
      title: "not “startup ideas”",
      content:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit.Officia, non.",
      createdAt: "3rd septamper, 2am",
    },
  ],
};

export const projectReducer = (state = INITIAL_STATE, action) => {
  return state;
};
