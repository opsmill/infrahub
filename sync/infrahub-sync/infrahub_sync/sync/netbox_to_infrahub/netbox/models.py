from typing import Any, List, Optional

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------




class CoreStandardGroup(NetboxModel):
    _modelname = "CoreStandardGroup"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;description&#34;,)




    name: str





    description: Optional[str]












    local_id: Optional[str]
    local_data: Optional[Any]







class BuiltinTag(NetboxModel):
    _modelname = "BuiltinTag"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;description&#34;,)




    name: str



    description: Optional[str]








    local_id: Optional[str]
    local_data: Optional[Any]



































































class InfraCircuit(NetboxModel):
    _modelname = "InfraCircuit"
    _identifiers = (&#34;circuit_id&#34;,)
    _attributes = (&#34;provider&#34;, &#34;type&#34;, &#34;tags&#34;, &#34;description&#34;, &#34;vendor_id&#34;)




    circuit_id: str



    description: Optional[str]



    vendor_id: Optional[str]








    provider: str





    type: str



    tags: List[str] = []







    local_id: Optional[str]
    local_data: Optional[Any]







class TemplateCircuitType(NetboxModel):
    _modelname = "TemplateCircuitType"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;tags&#34;, &#34;description&#34;)




    name: str



    description: Optional[str]








    tags: List[str] = []







    local_id: Optional[str]
    local_data: Optional[Any]





class InfraDevice(NetboxModel):
    _modelname = "InfraDevice"
    _identifiers = (&#34;name&#34;, &#34;location&#34;, &#34;rack&#34;, &#34;organization&#34;)
    _attributes = (&#34;model&#34;, &#34;role&#34;, &#34;tags&#34;, &#34;description&#34;, &#34;serial_number&#34;, &#34;asset_tag&#34;)




    name: Optional[str]



    description: Optional[str]



    serial_number: Optional[str]



    asset_tag: Optional[str]




    location: str



    model: str



    rack: Optional[str]





    role: Optional[str]







    tags: List[str] = []







    organization: Optional[str]









    local_id: Optional[str]
    local_data: Optional[Any]





class TemplateDeviceType(NetboxModel):
    _modelname = "TemplateDeviceType"
    _identifiers = (&#34;name&#34;, &#34;manufacturer&#34;)
    _attributes = (&#34;tags&#34;, &#34;part_number&#34;, &#34;height&#34;, &#34;full_depth&#34;)




    part_number: Optional[str]



    height: Optional[int]



    full_depth: Optional[bool]



    name: str










    manufacturer: str



    tags: List[str] = []







    local_id: Optional[str]
    local_data: Optional[Any]









class InfraIPAddress(NetboxModel):
    _modelname = "InfraIPAddress"
    _identifiers = (&#34;address&#34;, &#34;vrf&#34;)
    _attributes = (&#34;organization&#34;, &#34;description&#34;)




    address: str



    description: Optional[str]




    organization: Optional[str]







    vrf: Optional[str]









    local_id: Optional[str]
    local_data: Optional[Any]











class InfraProviderNetwork(NetboxModel):
    _modelname = "InfraProviderNetwork"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;provider&#34;, &#34;tags&#34;, &#34;description&#34;, &#34;vendor_id&#34;)




    name: str



    description: Optional[str]



    vendor_id: Optional[str]






    provider: str



    tags: List[str] = []









    local_id: Optional[str]
    local_data: Optional[Any]





class InfraPrefix(NetboxModel):
    _modelname = "InfraPrefix"
    _identifiers = (&#34;prefix&#34;, &#34;vrf&#34;)
    _attributes = (&#34;organization&#34;, &#34;role&#34;, &#34;description&#34;)




    prefix: str



    description: Optional[str]




    organization: Optional[str]









    role: Optional[str]





    vrf: Optional[str]











    local_id: Optional[str]
    local_data: Optional[Any]





class InfraRack(NetboxModel):
    _modelname = "InfraRack"
    _identifiers = (&#34;name&#34;, &#34;location&#34;)
    _attributes = (&#34;role&#34;, &#34;tags&#34;, &#34;height&#34;, &#34;facility_id&#34;, &#34;serial_number&#34;, &#34;asset_tag&#34;)




    name: str





    height: str



    facility_id: Optional[str]



    serial_number: Optional[str]



    asset_tag: Optional[str]




    location: str





    role: Optional[str]



    tags: List[str] = []







    local_id: Optional[str]
    local_data: Optional[Any]







class InfraRouteTarget(NetboxModel):
    _modelname = "InfraRouteTarget"
    _identifiers = (&#34;name&#34;, &#34;organization&#34;)
    _attributes = (&#34;description&#34;,)




    name: str



    description: Optional[str]




    organization: Optional[str]









    local_id: Optional[str]
    local_data: Optional[Any]





class InfraVLAN(NetboxModel):
    _modelname = "InfraVLAN"
    _identifiers = (&#34;name&#34;, &#34;vlan_id&#34;, &#34;location&#34;, &#34;vlan_group&#34;)
    _attributes = (&#34;organization&#34;, &#34;description&#34;)




    name: str



    description: Optional[str]



    vlan_id: int




    organization: Optional[str]



    location: Optional[str]









    vlan_group: Optional[str]







    local_id: Optional[str]
    local_data: Optional[Any]





class InfraVRF(NetboxModel):
    _modelname = "InfraVRF"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;organization&#34;, &#34;import_rt&#34;, &#34;export_rt&#34;, &#34;description&#34;, &#34;vrf_rd&#34;)




    name: str



    description: Optional[str]



    vrf_rd: Optional[str]




    organization: Optional[str]











    import_rt: List[str] = []



    export_rt: List[str] = []







    local_id: Optional[str]
    local_data: Optional[Any]





class CoreOrganization(NetboxModel):
    _modelname = "CoreOrganization"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;group&#34;, &#34;description&#34;, &#34;type&#34;)




    name: str





    description: Optional[str]



    type: Optional[str]






    group: Optional[str]







    local_id: Optional[str]
    local_data: Optional[Any]







class BuiltinRole(NetboxModel):
    _modelname = "BuiltinRole"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;description&#34;,)




    name: str





    description: Optional[str]








    local_id: Optional[str]
    local_data: Optional[Any]





class BuiltinLocation(NetboxModel):
    _modelname = "BuiltinLocation"
    _identifiers = (&#34;name&#34;,)
    _attributes = (&#34;organization&#34;, &#34;tags&#34;, &#34;group&#34;, &#34;description&#34;, &#34;type&#34;)




    name: str



    description: Optional[str]



    type: str






    organization: Optional[str]



    tags: List[str] = []



    group: Optional[str]











    local_id: Optional[str]
    local_data: Optional[Any]

































