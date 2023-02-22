QUERY = """
query ($repository_location: String!) {
    repository(location__value: $repository_location){
        name {
            value
        }
        location {
            value
        }
        username {
            value
        }
        password {
            value
        }
    }
}
"""
