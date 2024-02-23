from infrahub_sdk.checks import InfrahubCheck


class InfrahubCheckSpineNbrInterfaceDisabled(InfrahubCheck):
    query = "check_spine_interface_status"

    def validate(self, data):
        for device in data["device"]:
            device_name = device["name"]["value"]
            device_id = device["id"]

            nbr_intf_disabled = 0
            for intf in device["interfaces"]:
                if intf["enabled"]["value"] is False:
                    nbr_intf_disabled += 1

            if nbr_intf_disabled > 1:
                self.log_error(
                    message=f"{device_name} has {str(nbr_intf_disabled)} interfaces disabled, only 1 allowed.",
                    object_id=device_id,
                    object_type="device",
                )


INFRAHUB_CHECKS = [InfrahubCheckSpineNbrInterfaceDisabled]
