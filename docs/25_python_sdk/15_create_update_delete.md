---
label: Create & Update Nodes
layout: default
order: 650
---


## Create

+++ Async

#### Method 1
```python
from infrahub_client import InfrahubClient

client = await InfrahubClient.init(address="http://localhost:8000")
data = {"name": "johndoe", "label": "John Doe", "type": "User", "password": "J0esSecret!"}
obj = await client.create(kind="CoreAccount", data=data)
await obj.save()
print(f"New user created with the Id {obj.id}")
```

#### Method 2
```python
from infrahub_client import InfrahubClient

client = await InfrahubClient.init(address="http://localhost:8000")
obj = await client.create(kind="CoreAccount", name="janedoe", label="Jane Doe", type="User", password="J0esSecret!")
await obj.save()
print(f"New user created with the Id {obj.id}")
```

+++ Sync
#### Method 1
```python
from infrahub_client import InfrahubClientSync

client = InfrahubClientSync.init(address="http://localhost:8000")
data = {"name": "johndoe", "label": "John Doe", "type": "User", "password": "J0esSecret!"}
obj = client.create(kind="CoreAccount", data=data)
obj.save()
print(f"New user created with the Id {obj.id}")
```
#### Method 2
```python
from infrahub_client import InfrahubClientSync

client = InfrahubClientSync.init(address="http://localhost:8000")
obj = client.create(kind="CoreAccount", name="janedoe", label="Jane Doe", type="User", password="J0esSecret!")
obj.save()
print(f"New user created with the Id {obj.id}")
```
+++


## Update
+++ Async

```python
from infrahub_client import InfrahubClient

client = await InfrahubClient.init(address="http://localhost:8000")
obj = await client.get(kind="CoreAccount", name__value="admin")
obj.label.value = "Administrator"
await obj.save()
```

+++ Sync

```python
from infrahub_client import InfrahubClientSync

client = InfrahubClientSync.init(address="http://localhost:8000")
obj = client.get(kind="CoreAccount", name__value="admin")
obj.label.value = "Administrator"
obj.save()
```
+++


## Delete

+++ Async

```python
from infrahub_client import InfrahubClient

client = await InfrahubClient.init(address="http://localhost:8000")
obj = await client.get(kind="CoreAccount", name__value="johndoe")
await obj.delete()
```
+++ Sync
```python
from infrahub_client import InfrahubClientSync

client = InfrahubClientSync.init(address="http://localhost:8000")
obj = client.get(kind="CoreAccount", name__value="johndoe")
obj.delete()
```
+++

