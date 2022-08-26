# from infrahub.main import app

# from . import InfrahubCheck


# class InfrahubCheckInternal(InfrahubCheck):
#     def collect_data(self):
#         params = {"branch": self.branch_name, "rebase": self.rebase}
#         client = TestClient(app)

#         resp = client.post(f"/query/{self.query}", params=params)
#         resp.raise_for_status()
#         data = resp.json()
#         self.data = data
