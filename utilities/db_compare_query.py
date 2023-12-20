import time

import infrahub.config as config
from infrahub.database import execute_read_query_async

# pylint: skip-file

config.load_and_exit()

NBR_EXECUTION = 5

QUERY1 = """
MATCH (n:Status)
WHERE ID(n) = $node_id OR n.uuid = $node_id
WITH (n)
MATCH (n:Status)-[r1:HAS_ATTRIBUTE]->(a:Attribute)-[r2:HAS_VALUE]->(av:AttributeValue)
WHERE ((r1.branch = $branch1 AND r1.from < $time1 AND r1.to IS NULL)
 OR (r1.branch = $branch1 AND r1.from < $time1 AND r1.to > $time1)
 OR (r1.branch = $branch2 AND r1.from < $time2 AND r1.to IS NULL)
 OR (r1.branch = $branch2 AND r1.from < $time2 AND r1.to > $time2))
 AND ((r2.branch = $branch1 AND r2.from < $time1 AND r2.to IS NULL)
 OR (r2.branch = $branch1 AND r2.from < $time1 AND r2.to > $time1)
 OR (r2.branch = $branch2 AND r2.from < $time2 AND r2.to IS NULL)
 OR (r2.branch = $branch2 AND r2.from < $time2 AND r2.to > $time2))
RETURN n,a,av,r1
"""
PARAMS1 = {
    "node_id": "4206789f-0298-4b63-93b4-791ba496dd58",
    "branch1": "main",
    "branch2": "cr23",
    "time1": "2022-03-25T01:03:55.153344Z",
    # "time2": "current()",
    "time2": "2022-03-25T01:06:32.211798Z",
}


QUERY2 = """
MATCH (n) WHERE ID(n) = $node_id OR n.uuid = $node_id
MATCH (n)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE]-(av)
WHERE (
    (r1.branch = "main" AND r1.from < "2022-03-25T01:03:55.153344Z" AND r1.to IS NULL)
 OR (r1.branch = "main" AND r1.from < "2022-03-25T01:03:55.153344Z" AND r1.to > "2022-03-25T01:03:55.153344Z")
 OR (r1.branch = "cr23" AND r1.from < "2022-03-25T01:06:32.211774Z" AND r1.to IS NULL)
 OR (r1.branch = "cr23" AND r1.from < "2022-03-25T01:06:32.211774Z" AND r1.to > "2022-03-25T01:06:32.211774Z")
)
MATCH (n)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE]-(av)
WHERE (
    (r2.branch = "main" AND r2.from < "2022-03-25T01:03:55.153344Z" AND r2.to IS NULL)
 OR (r2.branch = "main" AND r2.from < "2022-03-25T01:03:55.153344Z" AND r2.to > "2022-03-25T01:03:55.153344Z")
 OR (r2.branch = "cr23" AND r2.from < "2022-03-25T01:06:32.211798Z" AND r2.to IS NULL)
 OR (r2.branch = "cr23" AND r2.from < "2022-03-25T01:06:32.211798Z" AND r2.to > "2022-03-25T01:06:32.211798Z")
)
RETURN n,a,av,r1
ORDER BY a.name, a.branch
"""
PARAMS2 = {"node_id": "3314b9e7-fcd8-4b89-91d7-04483d384fa5"}


async def compare_query():
    response_time1 = []
    response_time2 = []

    print("-- Execute Query 1 --- ")
    for i in range(0, NBR_EXECUTION):
        time_start = time.time()
        await execute_read_query_async(query=QUERY1, params=PARAMS1)
        response_time1.append(time.time() - time_start)

    print("-- Execute Query 2 --- ")
    for i in range(0, NBR_EXECUTION):
        time_start = time.time()
        await execute_read_query_async(query=QUERY2, params=PARAMS2)
        response_time2.append(time.time() - time_start)

    def time_to_ms(input):
        return f"{int(input * 1000)}ms"

    print("-----------------------------------------")
    avg1 = sum(response_time1) / len(response_time1)
    avg2 = sum(response_time1) / len(response_time1)
    print(f" Query 1 {time_to_ms(avg1)} | {[time_to_ms(x) for x in response_time1]}")
    print(f" Query 2 {time_to_ms(avg2)} | {[time_to_ms(x) for x in response_time2]}")
    if avg1 < avg2:
        print(f"  Query 1 is faster by {time_to_ms(avg2 - avg1)} {int((avg1 / avg2) * 100)}%")
    else:
        print(f"  Query 2 is faster by {time_to_ms(avg1 - avg2)} {int((avg2 / avg1) * 100)}%")
