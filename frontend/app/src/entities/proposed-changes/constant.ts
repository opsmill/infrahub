export const PROPOSED_CHANGE_APPROVAL_ACTIONS = {
  approve: {
    decision: "APPROVE",
    successMessage: "Proposed change approved!",
    errorMessage: "An error occured while approving the proposed change",
  },
  "cancel-approve": {
    decision: "CANCEL_APPROVE",
    successMessage: "Proposed change approval canceled!",
    errorMessage: "An error occured while canceling the proposed change approval",
  },
  reject: {
    decision: "REJECT",
    successMessage: "Proposed change rejected!",
    errorMessage: "An error occured while rejecting the proposed change",
  },
  "cancel-reject": {
    decision: "CANCEL_REJECT",
    successMessage: "Proposed change reject canceled!",
    errorMessage: "An error occured while canceling the proposed change reject",
  },
};

export const PROPOSED_CHANGE_STATE_ACTIONS = {
  merge: {
    state: "merge",
    successMessage: "Proposed change approved!",
    errorMessage: "An error occured while merging the proposed change",
  },
  close: {
    state: "close",
    successMessage: "Proposed change rejected!",
    errorMessage: "An error occured while closing the proposed change",
  },
  open: {
    state: "open",
    successMessage: "Proposed change opened!",
    errorMessage: "An error occured while opening the proposed change",
  },
};
