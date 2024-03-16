from infrahub_sdk.checks import InfrahubCheck


class CarDescription(InfrahubCheck):
    query = "car_overview"

    def validate(self, data: dict) -> None:
        for car in data["TestingCar"]["edges"]:
            name = car["node"]["name"]["value"]
            description = car["node"]["description"]["value"]
            if not description:
                self.log_error(message=f"The {name} car doesn't have a description, how will we sell it?")
