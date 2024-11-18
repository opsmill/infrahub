from infrahub.core.branch import Branch
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.database import InfrahubDatabase


async def test_use_percentage(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    net240 = ip_dataset_01["net240"]
    net240.member_type.value = PrefixMemberType.ADDRESS.value
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[net240])
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.0

    net240.member_type.value = PrefixMemberType.PREFIX.value
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[net240])
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.2197265625


async def test_use_percentage_no_prefixes(db: InfrahubDatabase, default_branch: Branch):
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[])
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.0
