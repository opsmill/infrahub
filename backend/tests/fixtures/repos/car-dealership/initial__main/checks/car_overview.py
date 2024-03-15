from infrahub_sdk.checks import InfrahubCheck


class CarDescription(InfrahubCheck):
    query = "car_overview"

    def validate(self, data: dict) -> None:
        for car in data["TestingCar"]["edges"]:
            name = car["node"]["status"]["value"]
            description = car["node"]["status"]["value"]
            if not description:
                self.log_error(message=f"The {name} car doesn't have a description, how will we sell it?")
