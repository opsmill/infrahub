from infrahub_sdk.checks import InfrahubCheck


class Check(InfrahubCheck):
    query = "car_owner_age"

    def validate(self, data: dict) -> None:
        owner = self.params["owner"]
        person = data["TestingPerson"]["edges"][0]["node"]
        number_of_cars = person["cars"]["count"]
        age = person["age"]["value"]
        if number_of_cars and age < 18:
            self.log_error(message=f"{owner} ({age}) is very young to own {number_of_cars} car(s)!")
        else:
            self.log_info(message=f"Check passed for {owner}, owner of {number_of_cars} car(s)")
