

## Create new Status Node
mutation {
  status_create(data: { slug: { value: "drained" }, label:{ value: "Drained"} }) {
    ok
    status {
      id
    }
  }
}


## Update descripton on a Status node
mutation {
  status_update(data: { id: "293ded0d-6451-4663-991a-582573c5c1a1", label:{ value: "Really Not Drained"} }) {
    ok
    status {
      id
      label {
        value
      }
    }
  }
}
