import logging
import time
import uuid
from collections import defaultdict
from ipaddress import IPv4Network, IPv6Network
from typing import Optional, cast

from infrahub_sdk import UUIDT, InfrahubClient, NodeStore
from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.protocols import (
    CoreAccount,
    CoreAccountGroup,
    CoreIPAddressPool,
    CoreIPPrefixPool,
    CoreStandardGroup,
    IpamNamespace,
)
from infrahub_sdk.protocols_base import CoreNode
from protocols import (
    InfraAutonomousSystem,
    InfraBGPSession,
    InfraCircuit,
    InfraCircuitEndpoint,
    InfraDevice,
    InfraInterfaceL2,
    InfraInterfaceL3,
    InfraLagInterfaceL2,
    InfraMlagDomain,
    InfraMlagInterfaceL2,
    InfraPlatform,
    InfraVLAN,
    IpamIPAddress,
    IpamIPPrefix,
    LocationCountry,
    LocationSite,
    OrganizationProvider,
)
from pydantic import BaseModel, ConfigDict, Field

PROFILES = {
    "small": {"num_sites": 2, "num_device_per_site": 2, "has_bgp_mesh": False, "has_branch": False},
    "medium": {"num_sites": 5, "num_device_per_site": 6, "has_bgp_mesh": True, "has_branch": True},
    "large": {"num_sites": 20, "num_device_per_site": 25, "has_bgp_mesh": False, "has_branch": False},
    "x-large": {"num_sites": 200, "num_device_per_site": 50, "has_bgp_mesh": False, "has_branch": False},
}


class ConfigError(Exception):
    pass


# Define the global configuration object
class GlobalConfig:
    def __init__(self) -> None:
        self.default_profile_name = "medium"
        self.num_sites = None
        self.num_device_per_site = None
        self.has_bgp_mesh = False
        self.has_branch = False

    def __set_config(self, num_sites: int, num_device_per_site: int, has_bgp_mesh: bool, has_branch: bool) -> None:
        # TODO: I guess it could be defined in the attribute itself?
        # Ensure that num_site is between boudaries
        if 1 <= int(num_sites) <= 200:
            self.num_sites = int(num_sites)
        else:
            raise ConfigError(f"Value for `num_sites` ({num_sites}) should be between 1 and 200.")

        # Ensure that num_device_per_site is between boudaries
        if 2 <= int(num_device_per_site) <= 100:
            self.num_device_per_site = int(num_device_per_site)
        else:
            raise ConfigError(f"Value for `num_device_per_site` ({num_device_per_site}) should be between 2 and 100.")

        self.has_bgp_mesh = has_bgp_mesh
        self.has_branch = has_branch

    def load_config(
        self,
        profile: str = None,
        num_sites: int = None,
        num_device_per_site: int = None,
        has_bgp_mesh: bool = None,
        has_branch: bool = None,
    ) -> None:
        if profile:
            # Warn user that we are going to ignore his input
            if num_sites or num_device_per_site or has_bgp_mesh or has_branch:
                raise ConfigError("You can't set additional config items if you've already provided a profile.")

            # Make sure profile exists
            if profile not in PROFILES:
                raise ConfigError(
                    f"Value for profile ({profile}) doesn't exist, please pick one among {PROFILES.keys()}."
                )

            # Load prebuilt profile
            profile_obj: dict = PROFILES[profile]
            self.__set_config(
                profile_obj["num_sites"],
                profile_obj["num_device_per_site"],
                profile_obj["has_bgp_mesh"],
                profile_obj["has_branch"],
            )
        else:
            # Load from manual arguments, if provided
            # If user only provides a part of the arguments e.g. only `number of site`
            # we fall back on medium profile by default
            default_profile: dict = PROFILES[self.default_profile_name]

            self.__set_config(
                num_sites=num_sites if num_sites is not None else default_profile["num_sites"],
                num_device_per_site=num_device_per_site
                if num_device_per_site is not None
                else default_profile["num_device_per_site"],
                has_bgp_mesh=has_bgp_mesh if has_bgp_mesh is not None else default_profile["has_bgp_mesh"],
                has_branch=has_branch if has_branch is not None else default_profile["has_branch"],
            )

    def __repr__(self) -> str:
        return f"Config(Sites: {self.num_sites}, Devices per site: {self.num_device_per_site}, BGP mesh: {self.has_bgp_mesh}, Additional branches: {self.has_branch})"


def translate_str_to_bool(key: str, value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise TypeError(f"Value for {key} should be 'True' or 'False'")


# pylint: skip-file
class Account(BaseModel):
    name: str
    password: str
    account_type: str
    role: str


class Asn(BaseModel):
    asn: int
    organization: str

    @property
    def name(self) -> str:
        return f"AS{self.asn}"


class BgpPeerGroup(BaseModel):
    name: str
    import_policies: str
    export_policies: str
    local_as: str
    remote_as: Optional[str] = Field(default=None)


class Device(BaseModel):
    name: str
    status: str
    type: str
    profile: str
    role: str
    tags: list[str]
    platform: str

    @property
    def l2_interface_names(self) -> list[str]:
        INTERFACE_L2_NAMES = {
            "7280R3": ["Ethernet11", "Ethernet12"],
            "ASR1002-HX": ["Ethernet11", "Ethernet12"],
            "MX204": ["et-0/0/3"],
            "7010TX-48": [f"Ethernet{idx}" for idx in range(1, 49)],
        }

        return INTERFACE_L2_NAMES.get(self.type, [])

    @property
    def l3_interface_names(self) -> list[str]:
        INTERFACE_L3_NAMES = {
            "7280R3": [
                "Ethernet1",
                "Ethernet2",
                "Ethernet3",
                "Ethernet4",
                "Ethernet5",
                "Ethernet6",
                "Ethernet7",
                "Ethernet8",
                "Ethernet9",
                "Ethernet10",
            ],
            "ASR1002-HX": [
                "Ethernet1",
                "Ethernet2",
                "Ethernet3",
                "Ethernet4",
                "Ethernet5",
                "Ethernet6",
                "Ethernet7",
                "Ethernet8",
                "Ethernet9",
                "Ethernet10",
            ],
            "7010TX-48": [],
            "MX204": ["et-0/0/0", "et-0/0/1", "et-0/0/2"],
        }
        return INTERFACE_L3_NAMES.get(self.type, [])


class Group(BaseModel):
    name: str
    label: str


class InterfaceProfile(BaseModel):
    name: str
    mtu: int
    kind: str

    @property
    def profile_kind(self) -> str:
        return f"Profile{self.kind}"


class P2pNetwork(BaseModel):
    site1: str
    site2: str
    edge: int
    circuit: str
    pool: Optional[IpamIPPrefix] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def identifier(self) -> str:
        return f"{self.site1_device}__{self.site2_device}"

    @property
    def site1_device(self) -> str:
        return f"{self.site1}-edge{self.edge}"

    @property
    def site2_device(self) -> str:
        return f"{self.site2}-edge{self.edge}"

    @property
    def provider_name(self) -> str:
        if self.edge == 1:
            return "Lumen"
        return "Zayo"

    def get_pool(self) -> IpamIPPrefix:
        if self.pool:
            return self.pool
        raise Exception("the variable pool hasn't been initilized yet")


class Platform(BaseModel):
    name: str
    nornir_platform: str
    napalm_driver: str
    netmiko_device_type: str
    ansible_network_os: str


class Organization(BaseModel):
    name: str
    type: str

    @property
    def kind(self) -> str:
        return f"Organization{self.type.title()}"


class Site(BaseModel):
    name: str
    country: str
    city: str
    contact: str


class Vlan(BaseModel):
    id: int
    role: str


CONTINENT_COUNTRIES = {
    "North America": ["United States of America", "Canada", "Mexico", "Nicaragua", "Haiti", "Puerto Rico"],
    "South America": ["Brazil", "South Africa", "Argentina", "Chile", "Peru", "Colombia", "Bolivia", "Ecuador"],
    "Africa": [
        "Morocco",
        "Kuwait",
        "Kenya",
        "Egypt",
        "Senegal",
        "Republic of Congo",
        "Ethiopia",
        "Tanzania",
        "Nigeria",
        "Ghana",
    ],
    "Europe": [
        "France",
        "Spain",
        "Italy",
        "Finland",
        "United Kingdom",
        "Greece",
        "Iceland",
        "Germany",
        "Norway",
        "Cyprus",
        "Lithuania",
        "Serbia",
        "Slovakia",
        "Croatia",
        "Bulgaria",
        "Latvia",
        "Poland",
        "Hungary",
        "Czech Republic",
        "Montenegro",
        "Bosnia and Herzegovina",
        "Belgium",
        "Estonia",
        "Sweden",
        "Denmark",
        "Russia",
        "Portugal",
        "Netherlands",
        "Switzerland",
    ],
    "Asia": [
        "Japan",
        "China",
        "Taiwan",
        "India",
        "Nepal",
        "Jordan",
        "Qatar",
        "Pakistan",
        "Malaysia",
        "South Korea",
        "Turkey",
        "United Arab Emirates",
        "Singapore",
        "Hong Kong",
        "Thailand",
    ],
    "Oceania": ["Australia", "New Zealand"],
}

# Chat GPT came up with the most cliche contact names here
SITES = [
    Site(name="sin", country="Singapore", city="Singapore", contact="Siti Tan"),
    Site(name="atl", country="United States of America", city="Atlanta", contact="Bailey Li"),
    Site(name="ord", country="United States of America", city="Chicago", contact="Kayden Kennedy"),
    Site(name="jfk", country="United States of America", city="New York", contact="Micaela Marsh"),
    Site(name="den", country="United States of America", city="Denver", contact="Francesca Wilcox"),
    Site(name="dfw", country="United States of America", city="Dallas", contact="Carmelo Moran"),
    Site(name="iad", country="United States of America", city="Washington D.C.", contact="Avery Jimenez"),
    Site(name="sea", country="United States of America", city="Seattle", contact="Charlotte Little"),
    Site(name="sfo", country="United States of America", city="San Francisco", contact="Taliyah Sampson"),
    Site(name="iah", country="United States of America", city="Houston", contact="Fernanda Solomon"),
    Site(name="mco", country="United States of America", city="Orlando", contact="Arthur Rose"),
    Site(name="yyz", country="Canada", city="Toronto", contact="Jaxon Fitzgerald"),
    Site(name="yvr", country="Canada", city="Vancouver", contact="Addison Harper"),
    Site(name="lhr", country="United Kingdom", city="London", contact="Isabella Harris"),
    Site(name="cdg", country="France", city="Paris", contact="Louis Dupont"),
    Site(name="nrt", country="Japan", city="Tokyo", contact="Haruto Sato"),
    Site(name="bom", country="India", city="Mumbai", contact="Aryan Patel"),
    Site(name="hkg", country="Hong Kong", city="Hong Kong", contact="Kai Wong"),
    Site(name="syd", country="Australia", city="Sydney", contact="Oliver Thompson"),
    Site(name="mad", country="Spain", city="Madrid", contact="Lucía García"),
    Site(name="fra", country="Germany", city="Frankfurt", contact="Lukas Müller"),
    Site(name="ams", country="Netherlands", city="Amsterdam", contact="Emma Visser"),
    Site(name="mxp", country="Italy", city="Milan", contact="Giulia Rossi"),
    Site(name="fco", country="Italy", city="Rome", contact="Alessandro Ferrari"),
    Site(name="osl", country="Norway", city="Oslo", contact="Nora Johansen"),
    Site(name="hel", country="Finland", city="Helsinki", contact="Oskari Virtanen"),
    Site(name="cph", country="Denmark", city="Copenhagen", contact="Freja Nielsen"),
    Site(name="zrh", country="Switzerland", city="Zurich", contact="Jonas Baumann"),
    Site(name="vce", country="Italy", city="Venice", contact="Sophia Romano"),
    Site(name="dxb", country="United Arab Emirates", city="Dubai", contact="Zayed Al Nahyan"),
    Site(name="jnb", country="South Africa", city="Johannesburg", contact="Thandiwe Ndlovu"),
    Site(name="gva", country="Switzerland", city="Geneva", contact="Chloe Dupont"),
    Site(name="bcn", country="Spain", city="Barcelona", contact="Carlos Martínez"),
    Site(name="lis", country="Portugal", city="Lisbon", contact="Maria Silva"),
    Site(name="ath", country="Greece", city="Athens", contact="Nikos Papadopoulos"),
    Site(name="ist", country="Turkey", city="Istanbul", contact="Ege Yılmaz"),
    Site(name="led", country="Russia", city="Saint Petersburg", contact="Vladimir Ivanov"),
    Site(name="svo", country="Russia", city="Moscow", contact="Olga Kuznetsova"),
    Site(name="blr", country="India", city="Bengaluru", contact="Neha Reddy"),
    Site(name="del", country="India", city="Delhi", contact="Rahul Sharma"),
    Site(name="bkk", country="Thailand", city="Bangkok", contact="Kanya Phrommin"),
    Site(name="hnd", country="Japan", city="Tokyo", contact="Yuki Tanaka"),
    Site(name="icn", country="South Korea", city="Seoul", contact="Jihoon Kim"),
    Site(name="kix", country="Japan", city="Osaka", contact="Rina Matsui"),
    Site(name="akl", country="New Zealand", city="Auckland", contact="Ethan Brown"),
    Site(name="kwi", country="Kuwait", city="Kuwait City", contact="Abdullah Al Sabah"),
    Site(name="cpt", country="South Africa", city="Cape Town", contact="Sipho Khumalo"),
    Site(name="pvg", country="China", city="Shanghai", contact="Wei Zhang"),
    Site(name="pek", country="China", city="Beijing", contact="Jia Li"),
    Site(name="hhg", country="China", city="Hong Kong", contact="Xin Wang"),
    Site(name="tpe", country="Taiwan", city="Taipei", contact="Mei Chen"),
    Site(name="cai", country="Egypt", city="Cairo", contact="Ahmed Hassan"),
    Site(name="lim", country="Peru", city="Lima", contact="Camila Flores"),
    Site(name="bog", country="Colombia", city="Bogotá", contact="Juan Hernández"),
    Site(name="lima", country="Peru", city="Lima", contact="Diego Ramos"),
    Site(name="sao", country="Brazil", city="São Paulo", contact="Gabriela Sousa"),
    Site(name="gig", country="Brazil", city="Rio de Janeiro", contact="Lucas Costa"),
    Site(name="mlu", country="United States of America", city="Monroe", contact="Samuel Grant"),
    Site(name="dtw", country="United States of America", city="Detroit", contact="Aaliyah Wright"),
    Site(name="pdx", country="United States of America", city="Portland", contact="Hayden Brooks"),
    Site(name="msp", country="United States of America", city="Minneapolis", contact="Jaxon Young"),
    Site(name="phx", country="United States of America", city="Phoenix", contact="Peyton Simmons"),
    Site(name="mia", country="United States of America", city="Miami", contact="Ariana Baker"),
    Site(name="bos", country="United States of America", city="Boston", contact="Scarlett Cook"),
    Site(name="las", country="United States of America", city="Las Vegas", contact="Ryder Griffin"),
    Site(name="clt", country="United States of America", city="Charlotte", contact="Skyler Ortiz"),
    Site(name="lax", country="United States of America", city="Los Angeles", contact="Noah Johnson"),
    Site(name="yul", country="Canada", city="Montreal", contact="Zoe Lambert"),
    Site(name="yyc", country="Canada", city="Calgary", contact="Grayson Scott"),
    Site(name="yeg", country="Canada", city="Edmonton", contact="Hannah Wright"),
    Site(name="nbo", country="Kenya", city="Nairobi", contact="Mwangi Otieno"),
    Site(name="acc", country="Ghana", city="Accra", contact="Kwame Mensah"),
    Site(name="lca", country="Cyprus", city="Larnaca", contact="Eleni Georgiou"),
    Site(name="tll", country="Estonia", city="Tallinn", contact="Kristo Vaher"),
    Site(name="vlc", country="Spain", city="Valencia", contact="Javier Torres"),
    Site(name="agp", country="Spain", city="Málaga", contact="Alejandro Romero"),
    Site(name="nap", country="Italy", city="Naples", contact="Valentina Ricci"),
    Site(name="flr", country="Italy", city="Florence", contact="Lorenzo Bianchi"),
    Site(name="sna", country="United States of America", city="Santa Ana", contact="Daniel Sanchez"),
    Site(name="vno", country="Lithuania", city="Vilnius", contact="Austėja Daukšaitė"),
    Site(name="beg", country="Serbia", city="Belgrade", contact="Nikola Marković"),
    Site(name="bts", country="Slovakia", city="Bratislava", contact="Jakub Horváth"),
    Site(name="dbv", country="Croatia", city="Dubrovnik", contact="Ivana Petrovic"),
    Site(name="zag", country="Croatia", city="Zagreb", contact="Filip Juric"),
    Site(name="sof", country="Bulgaria", city="Sofia", contact="Georgi Dimitrov"),
    Site(name="ktm", country="Nepal", city="Kathmandu", contact="Sunita Shrestha"),
    Site(name="rix", country="Latvia", city="Riga", contact="Kristaps Ozoliņš"),
    Site(name="waw", country="Poland", city="Warsaw", contact="Zofia Kowalska"),
    Site(name="gdn", country="Poland", city="Gdańsk", contact="Mateusz Nowak"),
    Site(name="krk", country="Poland", city="Krakow", contact="Jakub Wiśniewski"),
    Site(name="bud", country="Hungary", city="Budapest", contact="László Tóth"),
    Site(name="prg", country="Czech Republic", city="Prague", contact="Petra Novaková"),
    Site(name="bzv", country="Republic of Congo", city="Brazzaville", contact="Jules Ngoma"),
    Site(name="los", country="Nigeria", city="Lagos", contact="Chidi Okeke"),
    Site(name="add", country="Ethiopia", city="Addis Ababa", contact="Selamawit Haile"),
    Site(name="dar", country="Tanzania", city="Dar es Salaam", contact="Amani Njoroge"),
    Site(name="ktw", country="Poland", city="Katowice", contact="Alicja Zielińska"),
    Site(name="spu", country="Croatia", city="Split", contact="Milan Kovac"),
    Site(name="bio", country="Spain", city="Bilbao", contact="Miguel Fernandez"),
    Site(name="sjj", country="Bosnia and Herzegovina", city="Sarajevo", contact="Emir Kovačević"),
    Site(name="tgd", country="Montenegro", city="Podgorica", contact="Jovan Radović"),
    Site(name="tiv", country="Montenegro", city="Tivat", contact="Milica Petrović"),
    Site(name="rdu", country="United States of America", city="Raleigh", contact="Thomas Barnes"),
    Site(name="pit", country="United States of America", city="Pittsburgh", contact="Olivia Greene"),
    Site(name="slc", country="United States of America", city="Salt Lake City", contact="Brandon Cooper"),
    Site(name="mci", country="United States of America", city="Kansas City", contact="Samantha Lawrence"),
    Site(name="sat", country="United States of America", city="San Antonio", contact="Nicole Evans"),
    Site(name="oma", country="United States of America", city="Omaha", contact="Benjamin Davis"),
    Site(name="okc", country="United States of America", city="Oklahoma City", contact="Ethan Wood"),
    Site(name="abq", country="United States of America", city="Albuquerque", contact="Isabella Scott"),
    Site(name="tul", country="United States of America", city="Tulsa", contact="Carter Morris"),
    Site(name="hsv", country="United States of America", city="Huntsville", contact="Sophia Price"),
    Site(name="jan", country="United States of America", city="Jackson", contact="Logan Ross"),
    Site(name="ric", country="United States of America", city="Richmond", contact="Sydney Peterson"),
    Site(name="chs", country="United States of America", city="Charleston", contact="Aiden Mitchell"),
    Site(name="pvd", country="United States of America", city="Providence", contact="Maya Clark"),
    Site(name="bdl", country="United States of America", city="Hartford", contact="Kaitlyn Howard"),
    Site(name="bna", country="United States of America", city="Nashville", contact="Savannah Adams"),
    Site(name="msy", country="United States of America", city="New Orleans", contact="Noah Cooper"),
    Site(name="aus", country="United States of America", city="Austin", contact="Lily Martinez"),
    Site(name="lgb", country="United States of America", city="Long Beach", contact="Mason Torres"),
    Site(name="smf", country="United States of America", city="Sacramento", contact="Abigail Fisher"),
    Site(name="mem", country="United States of America", city="Memphis", contact="Isaac Jenkins"),
    Site(name="tpa", country="United States of America", city="Tampa", contact="Jacob Barnes"),
    Site(name="cle", country="United States of America", city="Cleveland", contact="Ella Simmons"),
    Site(name="buf", country="United States of America", city="Buffalo", contact="Daniel Bailey"),
    Site(name="cmh", country="United States of America", city="Columbus", contact="Avery Russell"),
    Site(name="ind", country="United States of America", city="Indianapolis", contact="Zoey Price"),
    Site(name="day", country="United States of America", city="Dayton", contact="Brianna Murphy"),
    Site(name="fll", country="United States of America", city="Fort Lauderdale", contact="Anthony Hayes"),
    Site(name="rsw", country="United States of America", city="Fort Myers", contact="Sofia Diaz"),
    Site(name="sdf", country="United States of America", city="Louisville", contact="Charles Bell"),
    Site(name="ict", country="United States of America", city="Wichita", contact="Eliana Myers"),
    Site(name="rno", country="United States of America", city="Reno", contact="Alyssa Powell"),
    Site(name="lga", country="United States of America", city="New York (LaGuardia)", contact="Ella King"),
    Site(name="ewr", country="United States of America", city="Newark", contact="Caleb Brooks"),
    Site(name="orh", country="United States of America", city="Worcester", contact="Harper Reed"),
    Site(name="bgr", country="United States of America", city="Bangor", contact="Isabella Walker"),
    Site(name="pwm", country="United States of America", city="Portland", contact="Charlotte Baker"),
    Site(name="ack", country="United States of America", city="Nantucket", contact="Oliver Foster"),
    Site(name="mht", country="United States of America", city="Manchester", contact="Liam Parker"),
    Site(name="acy", country="United States of America", city="Atlantic City", contact="Madison Griffin"),
    Site(name="jnu", country="United States of America", city="Juneau", contact="Ella Sanders"),
    Site(name="geg", country="United States of America", city="Spokane", contact="Emily Wood"),
    Site(name="slz", country="Brazil", city="São Luís", contact="Lucas Oliveira"),
    Site(name="for", country="Brazil", city="Fortaleza", contact="Gabriela Pereira"),
    Site(name="bel", country="Brazil", city="Belém", contact="Rafael Barbosa"),
    Site(name="nat", country="Brazil", city="Natal", contact="Isabela Souza"),
    Site(name="pso", country="Colombia", city="Pasto", contact="Camilo Suarez"),
    Site(name="mga", country="Nicaragua", city="Managua", contact="Luis Gutierrez"),
    Site(name="cus", country="Peru", city="Cusco", contact="Carla Espinoza"),
    Site(name="vvi", country="Bolivia", city="Santa Cruz", contact="Sergio Rivera"),
    Site(name="cuz", country="Peru", city="Cusco", contact="Vanessa Martinez"),
    Site(name="uio", country="Ecuador", city="Quito", contact="Santiago Herrera"),
    Site(name="pap", country="Haiti", city="Port-au-Prince", contact="Jean-Pierre Baptiste"),
    Site(name="sju", country="Puerto Rico", city="San Juan", contact="Carlos Rodriguez"),
    Site(name="pbi", country="United States of America", city="West Palm Beach", contact="Tiffany Young"),
    Site(name="cvg", country="United States of America", city="Cincinnati", contact="Grace Richardson"),
    Site(name="mdw", country="United States of America", city="Chicago", contact="Brianna Watson"),
    Site(name="bwi", country="United States of America", city="Baltimore", contact="Gabriel Stevens"),
    Site(name="phl", country="United States of America", city="Philadelphia", contact="Sophia Hill"),
    Site(name="lbb", country="United States of America", city="Lubbock", contact="Alyssa Wilson"),
    Site(name="scl", country="Chile", city="Santiago", contact="Gabriela Salazar"),
    Site(name="eze", country="Argentina", city="Buenos Aires", contact="Mateo Fernandez"),
    Site(name="gru", country="Brazil", city="São Paulo", contact="Renata Costa"),
    Site(name="lpa", country="Spain", city="Las Palmas", contact="Lucia Moreno"),
    Site(name="dkr", country="Senegal", city="Dakar", contact="Amadou Diop"),
    Site(name="svq", country="Spain", city="Seville", contact="Diego Ruiz"),
    Site(name="arn", country="Sweden", city="Stockholm", contact="Erik Lindström"),
    Site(name="bru", country="Belgium", city="Brussels", contact="Elise Dupont"),
    Site(name="gla", country="United Kingdom", city="Glasgow", contact="Ewan MacDonald"),
    Site(name="kef", country="Iceland", city="Reykjavik", contact="Birta Sigurðardóttir"),
    Site(name="amn", country="Jordan", city="Amman", contact="Layla Haddad"),
    Site(name="doh", country="Qatar", city="Doha", contact="Mohammed Al-Thani"),
    Site(name="khi", country="Pakistan", city="Karachi", contact="Ayesha Khan"),
    Site(name="bne", country="Australia", city="Brisbane", contact="Olivia Taylor"),
    Site(name="mel", country="Australia", city="Melbourne", contact="Jack Williams"),
    Site(name="kul", country="Malaysia", city="Kuala Lumpur", contact="Nurul Aisyah"),
    Site(name="dme", country="Russia", city="Moscow", contact="Olga Ivanova"),
    Site(name="tls", country="France", city="Toulouse", contact="Camille Dubois"),
    Site(name="mnl", country="Philippines", city="Manila", contact="Carlos Reyes"),
    Site(name="sgn", country="Vietnam", city="Ho Chi Minh City", contact="Thanh Nguyen"),
    Site(name="bhd", country="United Kingdom", city="Belfast", contact="Liam O'Connor"),
    Site(name="edi", country="United Kingdom", city="Edinburgh", contact="Euan Campbell"),
    Site(name="gdl", country="Mexico", city="Guadalajara", contact="Diego Hernandez"),
    Site(name="lih", country="United States of America", city="Lihue", contact="Brody Martinez"),
    Site(name="hba", country="Australia", city="Hobart", contact="Alice Wilson"),
    Site(name="maj", country="Marshall Islands", city="Majuro", contact="Pita Lamora"),
    Site(name="bgi", country="Barbados", city="Bridgetown", contact="Kiera Walker"),
    Site(name="pos", country="Trinidad and Tobago", city="Port of Spain", contact="Jasmine Lewis"),
    Site(name="ski", country="Norway", city="Ski", contact="Henrik Solheim"),
    Site(name="osy", country="North Macedonia", city="Ohrid", contact="Dimitri Petrov"),
    Site(name="nwi", country="United Kingdom", city="Norwich", contact="Oscar Turner"),
    Site(name="orn", country="Algeria", city="Oran", contact="Fatima Salah"),
    Site(name="tgu", country="Honduras", city="Tegucigalpa", contact="Ricardo Morales"),
    Site(name="hmo", country="Mexico", city="Hermosillo", contact="Valeria Lopez"),
    Site(name="gua", country="Guatemala", city="Guatemala City", contact="Mariana Castillo"),
    Site(name="plo", country="Australia", city="Port Lincoln", contact="Tyler Thompson"),
    Site(name="asm", country="Eritrea", city="Asmara", contact="Abiel Tesfay"),
    Site(name="luq", country="Argentina", city="San Luis", contact="Sofia Ramos"),
]

PLATFORMS = (
    Platform(
        name="Cisco IOS",
        nornir_platform="ios",
        napalm_driver="ios",
        netmiko_device_type="cisco_ios",
        ansible_network_os="ios",
    ),
    Platform(
        name="Cisco NXOS SSH",
        nornir_platform="nxos_ssh",
        napalm_driver="nxos_ssh",
        netmiko_device_type="cisco_nxos",
        ansible_network_os="nxos",
    ),
    Platform(
        name="Juniper JunOS",
        nornir_platform="junos",
        napalm_driver="junos",
        netmiko_device_type="juniper_junos",
        ansible_network_os="junos",
    ),
    Platform(
        name="Arista EOS",
        nornir_platform="eos",
        napalm_driver="eos",
        netmiko_device_type="arista_eos",
        ansible_network_os="eos",
    ),
)

DEVICES = (
    Device(
        name="edge1",
        status="active",
        type="7280R3",
        profile="profile1",
        role="edge",
        tags=["red", "green"],
        platform="Arista EOS",
    ),
    Device(
        name="edge2",
        status="active",
        type="ASR1002-HX",
        profile="profile1",
        role="edge",
        tags=["red", "blue", "green"],
        platform="Cisco IOS",
    ),
    Device(
        name="core1",
        status="drained",
        type="MX204",
        profile="profile1",
        role="core",
        tags=["blue"],
        platform="Juniper JunOS",
    ),
    Device(
        name="core2",
        status="provisioning",
        type="MX204",
        profile="profile1",
        role="core",
        tags=["red"],
        platform="Juniper JunOS",
    ),
    Device(
        name="leaf1",
        status="active",
        type="7010TX-48",
        profile="profile1",
        role="leaf",
        tags=["red", "green"],
        platform="Arista EOS",
    ),
    Device(
        name="leaf2",
        status="active",
        type="7010TX-48",
        profile="profile1",
        role="leaf",
        tags=["red", "green"],
        platform="Arista EOS",
    ),
)


NETWORKS_SUPERNET = IPv4Network("10.0.0.0/8")
NETWORKS_SUPERNET_IPV6 = IPv6Network("2001:DB8::/64")
NETWORKS_POOL_EXTERNAL_SUPERNET = IPv4Network("203.111.0.0/16")
MANAGEMENT_NETWORKS = IPv4Network("172.16.0.0/16")

ACTIVE_STATUS = "active"
BACKBONE_ROLE = "backbone"


def site_generator(nbr_site: int = 2) -> list[Site]:
    """Generate a list of site names by iterating over the list of SITES defined above and by increasing the id.

    site_names_generator(nbr_site=5)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1"]

    site_names_generator(nbr_site=12)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1", "iad1", "bkk1", "sfo1", "iah1", "mco1", "atl2", "ord2"]
    """

    sites: list[Site] = []

    # Calculate how many loop over the entire list we need to make
    # and how many site we need to generate on the last loop
    nbr_loop = (int(nbr_site / len(SITES))) + 1
    nbr_last_loop = nbr_site % len(SITES) or len(SITES)

    for idx in range(1, 1 + nbr_loop):
        nbr_this_loop = len(SITES)
        if idx == nbr_loop:
            nbr_this_loop = nbr_last_loop

        sites.extend(
            [
                Site(name=f"{site.name}{idx}", country=site.country, city=site.city, contact=site.contact)
                for site in SITES[:nbr_this_loop]
            ]
        )

    return sites


INTERFACE_MGMT_NAME = {
    "7280R3": "Management0",
    "7010TX-48": "Management0",
    "ASR1002-HX": "Management0",
    "MX204": "MGMT",
}


LAG_INTERFACE_L2 = {
    "7280R3": [{"name": "port-channel1", "lacp": "Active", "members": ["Ethernet11", "Ethernet12"]}],
    "7010TX-48": [
        {
            "name": "port-channel1",
            "description": "MLAG peer link",
            "lacp": "Active",
            "members": ["Ethernet1", "Ethernet2"],
        },
        {
            "name": "port-channel2",
            "description": "MLAG to Server",
            "lacp": "Active",
            "members": ["Ethernet5", "Ethernet6"],
        },
    ],
}

INTERFACE_L3_ROLES_MAPPING = {
    "edge": [
        "peer",
        "peer",
        "backbone",
        "backbone",
        "upstream",
        "upstream",
        "spare",
        "spare",
        "peering",
        "spare",
        "spare",
        "spare",
    ],
    "core": [
        "backbone",
        "backbone",
        "backbone",
        "spare",
    ],
    "leaf": [],
}

INTERFACE_L2_ROLES_MAPPING = {
    "leaf": [
        "peer",
        "peer",
    ],
}

LAG_INTERFACE_L2_ROLES_MAPPING: dict[str, dict[str, str]] = {
    "leaf": {"port-channel1": "peer", "port-channel2": "server"}
}

INTERFACE_L2_MODE_MAPPING = {"peer": "Trunk (ALL)"}

MLAG_DOMAINS = {"leaf": {"domain_id": 1, "peer_interfaces": ["port-channel1", "port-channel1"]}}

MLAG_INTERFACE_L2 = {
    "leaf": [
        {
            "mlag_id": 2,
            "mlag_domain": 1,
            "members": ["port-channel2", "port-channel2"],
        }
    ]
}

TAGS = ["blue", "green", "red"]

ORGANIZATIONS = (
    Organization(name="Arelion", type="provider"),
    Organization(name="Colt Technology Services", type="provider"),
    Organization(name="Verizon Business", type="provider"),
    Organization(name="GTT Communications", type="provider"),
    Organization(name="Hurricane Electric", type="provider"),
    Organization(name="Lumen", type="provider"),
    Organization(name="Zayo", type="provider"),
    Organization(name="Equinix", type="provider"),
    Organization(name="Interxion", type="provider"),
    Organization(name="PCCW Global", type="provider"),
    Organization(name="Orange S.A", type="provider"),
    Organization(name="Tata Communications", type="provider"),
    Organization(name="Sprint", type="provider"),
    Organization(name="NTT America", type="provider"),
    Organization(name="Cogent Communications", type="provider"),
    Organization(name="Comcast Cable Communication", type="provider"),
    Organization(name="Telecom Italia Sparkle", type="provider"),
    Organization(name="AT&T Services", type="provider"),
    Organization(name="Duff", type="tenant"),
    Organization(name="Juniper", type="manufacturer"),
    Organization(name="Cisco", type="manufacturer"),
    Organization(name="Arista", type="manufacturer"),
)

ASNS = (
    Asn(asn=1299, organization="Arelion"),
    Asn(asn=64496, organization="Duff"),
    Asn(asn=8220, organization="Colt Technology Services"),
    Asn(asn=701, organization="Verizon Business"),
    Asn(asn=3257, organization="GTT Communications"),
    Asn(asn=6939, organization="Hurricane Electric"),
    Asn(asn=3356, organization="Lumen"),
    Asn(asn=6461, organization="Zayo"),
    Asn(asn=24115, organization="Equinix"),
    Asn(asn=20710, organization="Interxion"),
    Asn(asn=3491, organization="PCCW Global"),
    Asn(asn=5511, organization="Orange S.A"),
    Asn(asn=6453, organization="Tata Communications"),
    Asn(asn=1239, organization="Sprint"),
    Asn(asn=2914, organization="NTT America"),
    Asn(asn=174, organization="Cogent Communications"),
    Asn(asn=7922, organization="Comcast Cable Communication"),
    Asn(asn=6762, organization="Telecom Italia Sparkle"),
    Asn(asn=7018, organization="AT&T Services"),
)

INTERFACE_OBJS: dict[str, list[InfraInterfaceL3]] = defaultdict(list)

ACCOUNTS = (
    Account(name="pop-builder", account_type="Script", password="Password123", role="read-write"),
    Account(name="CRM Synchronization", account_type="Script", password="Password123", role="read-write"),
    Account(name="Jack Bauer", account_type="User", password="Password123", role="read-only"),
    Account(name="Chloe O'Brian", account_type="User", password="Password123", role="read-write"),
    Account(name="David Palmer", account_type="User", password="Password123", role="read-write"),
    Account(name="Operation Team", account_type="User", password="Password123", role="read-only"),
    Account(name="Engineering Team", account_type="User", password="Password123", role="read-write"),
    Account(name="Architecture Team", account_type="User", password="Password123", role="read-only"),
)


GROUPS = (
    Group(name="edge_router", label="Edge Router"),
    Group(name="core_router", label="Core Router"),
    Group(name="cisco_devices", label="Cisco Devices"),
    Group(name="arista_devices", label="Arista Devices"),
    Group(name="upstream_interfaces", label="Upstream Interfaces"),
    Group(name="backbone_interfaces", label="Backbone Interfaces"),
    Group(name="maintenance_circuits", label="Circuits in Maintenance"),
    Group(name="provisioning_circuits", label="Circuits in Provisioning"),
    Group(name="backbone_services", label="Backbone Services"),
)

BGP_PEER_GROUPS = (
    BgpPeerGroup(
        name="POP_INTERNAL",
        import_policies="IMPORT_INTRA_POP",
        export_policies="EXPORT_INTRA_POP",
        local_as="Duff",
        remote_as="Duff",
    ),
    BgpPeerGroup(
        name="POP_GLOBAL",
        import_policies="IMPORT_POP_GLOBAL",
        export_policies="EXPORT_POP_GLOBLA",
        local_as="Duff",
        remote_as=None,
    ),
    BgpPeerGroup(
        name="UPSTREAM_DEFAULT",
        import_policies="IMPORT_UPSTREAM",
        export_policies="EXPORT_PUBLIC_PREFIX",
        local_as="Duff",
        remote_as=None,
    ),
    BgpPeerGroup(
        name="UPSTREAM_ARELION",
        import_policies="IMPORT_UPSTREAM",
        export_policies="EXPORT_PUBLIC_PREFIX",
        local_as="Duff",
        remote_as="Arelion",
    ),
    BgpPeerGroup(
        name="IX_DEFAULT",
        import_policies="IMPORT_IX",
        export_policies="EXPORT_PUBLIC_PREFIX",
        local_as="Duff",
        remote_as=None,
    ),
)

INTERFACE_PROFILES = (
    InterfaceProfile(name="upstream_profile", mtu=1515, kind="InfraInterfaceL3"),
    InterfaceProfile(name="backbone_profile", mtu=9216, kind="InfraInterfaceL3"),
)

VLANS = (
    Vlan(id=200, role="server"),
    Vlan(id=400, role="management"),
)

store = NodeStore()


async def apply_interface_profiles(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    # ------------------------------------------
    # Add profile on interfaces upstream/backbone
    # ------------------------------------------
    log.info("Starting to apply profiles to interfaces")
    upstream_interfaces = await client.filters(branch=branch, kind=InfraInterfaceL3, role__value="upstream")
    backbone_interfaces = await client.filters(branch=branch, kind=InfraInterfaceL3, role__value="backbone")
    upstream_profile = store.get(key="upstream_profile", kind="ProfileInfraInterfaceL3", raise_when_missing=True)
    backbone_profile = store.get(key="backbone_profile", kind="ProfileInfraInterfaceL3", raise_when_missing=True)

    batch = await client.create_batch()
    for interface in upstream_interfaces:
        batch.add(
            task=interface.add_relationships,
            node=interface,
            relation_to_update="profiles",
            related_nodes=[upstream_profile.id],
        )

    for interface in backbone_interfaces:
        batch.add(
            task=interface.add_relationships,
            node=interface,
            relation_to_update="profiles",
            related_nodes=[backbone_profile.id],
        )

    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")

    log.info("Done applying profiles to interfaces")


async def create_backbone_connectivity(
    client: InfrahubClient, log: logging.Logger, branch: str, num_sites: int
) -> None:
    # --------------------------------------------------
    # CREATE Backbone Links & Circuits
    # --------------------------------------------------
    log.info("Creating Backbone Links & Circuits")
    account_pop = store.get("pop-builder", kind=CoreAccount, raise_when_missing=True)
    interconnection_pool = store.get("interconnection_pool", kind=CoreAccount, raise_when_missing=True)

    networks: list[P2pNetwork] = []

    if num_sites > 1:
        networks.append(P2pNetwork(site1="atl1", site2="ord1", edge=1, circuit="DUFF-1543451"))
        networks.append(P2pNetwork(site1="atl1", site2="ord1", edge=2, circuit="DUFF-8263953"))
    if num_sites > 2:
        networks.append(P2pNetwork(site1="atl1", site2="jfk1", edge=1, circuit="DUFF-6535773"))
        networks.append(P2pNetwork(site1="atl1", site2="jfk1", edge=2, circuit="DUFF-7324064"))
        networks.append(P2pNetwork(site1="jfk1", site2="ord1", edge=1, circuit="DUFF-5826854"))
        networks.append(P2pNetwork(site1="jfk1", site2="ord1", edge=2, circuit="DUFF-4867430"))

    for network in networks:
        network.pool = await client.allocate_next_ip_prefix(
            resource_pool=interconnection_pool, kind=IpamIPPrefix, branch=branch, identifier=network.identifier
        )

    log.info("- Done allocating addresses")

    for backbone_link in networks:
        intf1 = INTERFACE_OBJS[backbone_link.site1_device].pop(0)
        intf2 = INTERFACE_OBJS[backbone_link.site2_device].pop(0)

        backbone_link_ips = backbone_link.get_pool().prefix.value.hosts()

        provider = store.get(kind="OrganizationProvider", key=backbone_link.provider_name)
        obj = await client.create(
            branch=branch,
            kind=InfraCircuit,
            description=f"Backbone {backbone_link.site1} <-> {backbone_link.site2}",
            circuit_id=backbone_link.circuit,
            vendor_id=f"{backbone_link.provider_name.upper()}-{UUIDT().short()}",
            provider=provider,
            status=ACTIVE_STATUS,
            role=BACKBONE_ROLE,
        )
        await obj.save()
        log.info(f"- Created {obj._schema.kind} - {backbone_link.provider_name} [{obj.vendor_id.value}]")

        # Create Circuit Endpoints
        endpoint1 = await client.create(
            branch=branch,
            kind=InfraCircuitEndpoint,
            description=f"Endpoint {backbone_link.circuit} to {backbone_link.site1_device}",
            site=backbone_link.site1,
            circuit=obj,
            connected_endpoint=intf1,
        )
        await endpoint1.save()

        endpoint2 = await client.create(
            branch=branch,
            kind=InfraCircuitEndpoint,
            description=f"Endpoint {backbone_link.circuit} to {backbone_link.site2_device}",
            site=backbone_link.site2,
            circuit=obj,
            connected_endpoint=intf2,
        )
        await endpoint2.save()

        # Create IP Address
        intf11_address = f"{str(next(backbone_link_ips))}/31"
        intf21_address = f"{str(next(backbone_link_ips))}/31"
        intf11_ip = await client.create(
            branch=branch,
            kind=IpamIPAddress,
            interface={"id": intf1.id, "source": account_pop.id},
            address={"value": intf11_address, "source": account_pop.id},
        )
        await intf11_ip.save()
        intf21_ip = await client.create(
            branch=branch,
            kind=IpamIPAddress,
            interface={"id": intf2.id, "source": account_pop.id},
            address={"value": intf21_address, "source": account_pop.id},
        )
        await intf21_ip.save()

        # Update Interface
        intf11 = await client.get(branch=branch, kind=InfraInterfaceL3, id=intf1.id)
        intf11.description.value = f"Backbone: Connected to {backbone_link.site2_device} via {backbone_link.circuit}"
        await intf11.save()

        intf21 = await client.get(branch=branch, kind=InfraInterfaceL3, id=intf2.id)
        intf21.description.value = f"Backbone: Connected to {backbone_link.site1_device} via {backbone_link.circuit}"
        await intf21.save()

        log.info(
            f" - Connected '{backbone_link.site1_device}::{intf1.name.value}' <> '{backbone_link.site2_device}::{intf2.name.value}'"
        )


async def create_bgp_mesh(client: InfrahubClient, log: logging.Logger, branch: str, sites: list[Site]) -> None:
    # --------------------------------------------------
    # CREATE Full Mesh iBGP SESSION between all the Edge devices
    # --------------------------------------------------
    log.info("Creating Full Mesh iBGP SESSION between all the Edge devices")
    batch = await client.create_batch()
    num_sites = len(sites)
    internal_as = store.get(kind=InfraAutonomousSystem, key="Duff", raise_when_missing=True)

    for site1 in sites:
        for site2 in sites:
            if site1 == site2:
                continue

            for idx1 in range(1, min(3, num_sites)):
                for idx2 in range(1, min(3, num_sites)):
                    device1 = f"{site1.name}-edge{idx1}"
                    device2 = f"{site2.name}-edge{idx2}"

                    loopback1 = store.get(key=f"{device1}-loopback", kind=InfraInterfaceL3, raise_when_missing=True)
                    loopback2 = store.get(key=f"{device2}-loopback", kind=InfraInterfaceL3, raise_when_missing=True)

                    peer_group_name = "POP_GLOBAL"

                    obj = await client.create(
                        branch=branch,
                        kind="InfraBGPSession",
                        type="INTERNAL",
                        local_as=internal_as.id,
                        local_ip=loopback1.id,
                        remote_as=internal_as.id,
                        remote_ip=loopback2.id,
                        peer_group=store.get(key=peer_group_name, raise_when_missing=True).id,
                        device=store.get(kind=InfraDevice, key=device1, raise_when_missing=True).id,
                        status=ACTIVE_STATUS,
                        role=BACKBONE_ROLE,
                    )
                    batch.add(task=obj.save, node=obj)

    async for node, _ in batch.execute():
        if node._schema.default_filter:
            accessor = f"{node._schema.default_filter.split('__')[0]}"
            log.info(f"{node._schema.kind} {getattr(node, accessor).value} - Creation Completed")
        else:
            log.info(f"{node} - Creation Completed")


async def generate_site_vlans(
    client: InfrahubClient, log: logging.Logger, branch: str, site: Site, site_id: int
) -> None:
    account_pop = store.get("pop-builder", kind=CoreAccount, raise_when_missing=True)
    group_eng = store.get("Engineering Team", kind=CoreAccount, raise_when_missing=True)
    group_ops = store.get("Operation Team", kind=CoreAccount, raise_when_missing=True)

    for vlan in VLANS:
        vlan_name = f"{site.name}_{vlan.role}"
        obj = await client.create(
            branch=branch,
            kind=InfraVLAN,
            site={"id": site_id, "source": account_pop.id, "is_protected": True},
            name={"value": vlan_name, "is_protected": True, "source": account_pop.id},
            vlan_id={"value": vlan.id, "is_protected": True, "owner": group_eng.id, "source": account_pop.id},
            status={"value": ACTIVE_STATUS, "owner": group_ops.id},
            role={"value": vlan.role, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
        )
        await obj.save()
        store.set(key=vlan_name, node=obj)


async def generate_site_mlag_domain(client: InfrahubClient, log: logging.Logger, branch: str, site: Site) -> None:
    # --------------------------------------------------
    # Set up MLAG domains
    # --------------------------------------------------
    for role, domain in MLAG_DOMAINS.items():
        devices = [
            store.get(kind=InfraDevice, key=f"{site.name}-{role}1"),
            store.get(kind=InfraDevice, key=f"{site.name}-{role}2"),
        ]
        name = f"{site.name}-{role}-12"

        peer_interfaces = [
            store.get(kind=InfraLagInterfaceL2, key=f"{device_obj.name.value}-lagl2-{domain['peer_interfaces'][idx]}")  # type: ignore[index]
            for idx, device_obj in enumerate(devices)
        ]

        mlag_domain = await client.create(
            kind=InfraMlagDomain,
            name=name,
            domain_id=domain["domain_id"],
            devices=devices,
            peer_interfaces=peer_interfaces,
        )

        await mlag_domain.save()
        store.set(key=f"mlag-domain-{name}", node=mlag_domain)

    # --------------------------------------------------
    # Set up MLAG Interfaces
    # --------------------------------------------------
    for role, mlags in MLAG_INTERFACE_L2.items():
        devices = [
            store.get(kind=InfraDevice, key=f"{site.name}-{role}1"),
            store.get(kind=InfraDevice, key=f"{site.name}-{role}2"),
        ]

        for mlag in mlags:
            members = [
                store.get(kind=InfraLagInterfaceL2, key=f"{device_obj.name.value}-lagl2-{mlag['members'][idx]}")  # type: ignore[index]
                for idx, device_obj in enumerate(devices)
            ]
            mlag_domain = store.get(kind=InfraMlagDomain, key=f"mlag-domain-{site.name}-{role}-12")

            mlag_interface = await client.create(
                kind=InfraMlagInterfaceL2, mlag_domain=mlag_domain, mlag_id=mlag["mlag_id"], members=members
            )

            await mlag_interface.save()


async def generate_site(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    site: Site,
    interconnection_pool: CoreNode,
    loopback_pool: CoreNode,
    management_pool: CoreNode,
    external_pool: CoreNode,
) -> str:
    group_eng = store.get("Engineering Team", kind=CoreAccount)
    group_ops = store.get("Operation Team", kind=CoreAccount)
    account_pop = store.get("pop-builder", kind=CoreAccount)
    account_crm = store.get("CRM Synchronization", kind=CoreAccount)
    internal_as = store.get(kind=InfraAutonomousSystem, key="Duff")

    country = store.get(kind=LocationCountry, key=site.country)
    # --------------------------------------------------
    # Create the Site
    # --------------------------------------------------
    site_obj = await client.create(
        branch=branch,
        kind="LocationSite",
        name={"value": site.name, "is_protected": True, "source": account_crm.id},
        contact={"value": site.contact, "is_protected": True, "source": account_crm.id},
        city={"value": site.city, "is_protected": True, "source": account_crm.id},
        parent=country,
    )
    await site_obj.save()
    log.info(f"- Created {site_obj._schema.kind} - {site.name}")

    await generate_site_vlans(client=client, log=log, branch=branch, site=site, site_id=site_obj.id)

    # --------------------------------------------------
    # Create the site specific IP prefixes
    # --------------------------------------------------
    peer_networks: list[IpamIPPrefix] = [
        await client.allocate_next_ip_prefix(resource_pool=interconnection_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=interconnection_pool, kind=IpamIPPrefix, branch=branch),
    ]
    peer_network_hosts = {0: peer_networks[0].prefix.value.hosts(), 1: peer_networks[1].prefix.value.hosts()}

    group_core_router_members: list[str] = []
    group_edge_router_members: list[str] = []
    group_cisco_devices_members: list[str] = []
    group_arista_devices_members: list[str] = []
    group_upstream_interfaces_members = []
    group_backbone_interfaces_members = []

    for idx, device in enumerate(DEVICES):
        device_name = f"{site.name}-{device.name}"
        platform_id = store.get(kind=InfraPlatform, key=device.platform).id

        obj = await client.create(
            branch=branch,
            kind=InfraDevice,
            site={"id": site_obj.id, "source": account_pop.id, "is_protected": True},
            name={"value": device_name, "source": account_pop.id, "is_protected": True},
            status={"value": device.status, "owner": group_ops.id},
            type={"value": device.type, "source": account_pop.id},
            role={"value": device.role, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            asn={"id": internal_as.id, "source": account_pop.id, "is_protected": True, "owner": group_eng.id},
            tags=[store.get(kind="BuiltinTag", key=tag_name, raise_when_missing=True).id for tag_name in device.tags],
            platform={"id": platform_id, "source": account_pop.id, "is_protected": True},
        )
        await obj.save()
        store.set(key=device_name, node=obj)
        log.info(f"- Created {obj._schema.kind} - {obj.name.value}")

        # Add device to groups
        if "edge" in device.role:
            group_edge_router_members.append(obj.id)
        elif "core" in device.role:
            group_core_router_members.append(obj.id)

        if "Arista" in device.platform:
            group_arista_devices_members.append(obj.id)
        elif "Cisco" in device.platform:
            group_cisco_devices_members.append(obj.id)

        # Loopback Interface
        intf = await client.create(
            branch=branch,
            kind=InfraInterfaceL3,
            device={"id": obj.id, "is_protected": True},
            name={"value": "Loopback0", "source": account_pop.id, "is_protected": True},
            enabled=True,
            status=ACTIVE_STATUS,
            role="loopback",
            speed=1000,
        )
        await intf.save()

        ip = await client.allocate_next_ip_address(
            resource_pool=loopback_pool, identifier=device_name, data={"interface": intf.id}, branch=branch
        )
        store.set(key=f"{device_name}-loopback", node=ip)

        # Management Interface
        intf = await client.create(
            branch=branch,
            kind=InfraInterfaceL3,
            device={"id": obj.id, "is_protected": True},
            name={"value": INTERFACE_MGMT_NAME[device.type], "source": account_pop.id},
            enabled={"value": True, "owner": group_eng.id},
            status={"value": ACTIVE_STATUS, "owner": group_eng.id},
            role={"value": "management", "source": account_pop.id, "is_protected": True},
            speed=1000,
        )
        await intf.save()
        management_ip = await client.allocate_next_ip_address(
            resource_pool=management_pool, identifier=device_name, data={"interface": intf.id}, branch=branch
        )
        management_ip = cast(IpamIPAddress, management_ip)

        # set the IP address of the device to the management interface IP address
        obj.primary_address = management_ip  # type: ignore[assignment]
        await obj.save()

        # L3 Interfaces
        for intf_idx, intf_name in enumerate(device.l3_interface_names):
            intf_role = INTERFACE_L3_ROLES_MAPPING[device.role][intf_idx]

            intf = await client.create(
                branch=branch,
                kind=InfraInterfaceL3,
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
            )
            await intf.save()

            store.set(key=f"{device_name}-l3-{intf_idx}", node=intf)
            if intf_role == "backbone":
                INTERFACE_OBJS[device_name].append(intf)
                group_backbone_interfaces_members.append(intf.id)

            subnet = None
            address = None
            if intf_role == "peer":
                address = f"{str(next(peer_network_hosts[intf_idx]))}/31"

            if intf_role == "upstream":
                group_upstream_interfaces_members.append(intf.id)

            if intf_role in ["upstream", "peering"] and "edge" in device.role:
                subnet = await client.allocate_next_ip_prefix(
                    kind=IpamIPPrefix,
                    resource_pool=external_pool,
                    identifier=f"{device_name}__{intf_role}__{intf_idx}",
                    branch=branch,
                )
                subnet_hosts = subnet.prefix.value.hosts()
                address = f"{str(next(subnet_hosts))}/29"
                peer_address = f"{str(next(subnet_hosts))}/29"

            if address:
                ip = await client.create(
                    branch=branch,
                    kind=IpamIPAddress,
                    interface={"id": intf.id, "source": account_pop.id},
                    address={"value": address, "source": account_pop.id},
                )
                await ip.save()

            # Create Circuit and BGP session for upstream and peering
            if intf_role in ["upstream", "peering"]:
                circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-{intf_role}-{address}"))))[24:]
                circuit_id = f"DUFF-{circuit_id_unique}"
                upstream_providers = ["Arelion", "Colt Technology Services"]

                if intf_role == "upstream":
                    provider_name = upstream_providers[intf_idx % 2]
                elif intf_role == "peering":
                    provider_name = "Equinix"

                provider = store.get(kind=OrganizationProvider, key=provider_name, raise_when_missing=True)

                circuit = await client.create(
                    branch=branch,
                    kind=InfraCircuit,
                    circuit_id=circuit_id,
                    vendor_id=f"{provider_name.upper()}-{UUIDT().short()}",
                    provider=provider.id,
                    status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                    role={"value": intf_role, "source": account_pop.id, "owner": group_eng.id},
                )
                await circuit.save()
                log.info(f" - Created {circuit._schema.kind} - {provider_name} [{circuit.vendor_id.value}]")

                endpoint1 = await client.create(
                    branch=branch,
                    kind=InfraCircuitEndpoint,
                    site=site_obj,
                    circuit=circuit.id,
                    connected_endpoint=intf.id,
                )
                await endpoint1.save()

                intf.description.value = f"Connected to {provider_name} via {circuit_id}"

                if intf_role == "upstream":
                    peer_group_name = (
                        "UPSTREAM_ARELION" if "arelion" in provider.name.value.lower() else "UPSTREAM_DEFAULT"
                    )

                    peer_ip = await client.create(
                        branch=branch,
                        kind=IpamIPAddress,
                        address=peer_address,
                    )
                    await peer_ip.save()

                    peer_as = store.get(kind=InfraAutonomousSystem, key=provider_name)
                    bgp_session = await client.create(
                        branch=branch,
                        kind=InfraBGPSession,
                        type="EXTERNAL",
                        local_as=internal_as.id,
                        local_ip=ip.id,
                        remote_as=peer_as.id,
                        remote_ip=peer_ip.id,
                        peer_group=store.get(key=peer_group_name, raise_when_missing=True).id,
                        device=store.get(key=device_name, raise_when_missing=True).id,
                        status=ACTIVE_STATUS,
                        role=intf_role,
                    )
                    await bgp_session.save()

                    await circuit.add_relationships(relation_to_update="bgp_sessions", related_nodes=[bgp_session.id])
                    log.debug(
                        f" - Created BGP Session '{device_name}' >> '{provider_name}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
                    )

        # L2 Interfaces
        batch = await client.create_batch()

        for intf_idx, intf_name in enumerate(device.l2_interface_names):
            try:
                intf_role = INTERFACE_L2_ROLES_MAPPING.get(device.role, [])[intf_idx]
            except IndexError:
                intf_role = "server"

            l2_mode = INTERFACE_L2_MODE_MAPPING.get(intf_role, "Access")

            untagged_vlan = None
            if l2_mode == "Access":
                untagged_vlan = store.get(kind=InfraVLAN, key=f"{site.name}_server")

            intf = await client.create(
                branch=branch,
                kind=InfraInterfaceL2,
                device={"id": obj.id, "is_protected": True},
                name=intf_name,
                speed=10000,
                enabled=True,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
                l2_mode=l2_mode,
                untagged_vlan=untagged_vlan,
            )

            batch.add(task=intf.save, node=intf)
            store.set(key=f"{device_name}-l2-{intf_name}", node=intf)

        async for node, _ in batch.execute():
            log.debug(f"- Created {node._schema.kind} - {node.name.value}")

        for lag_intf in LAG_INTERFACE_L2.get(device.type, []):
            try:
                intf_role = LAG_INTERFACE_L2_ROLES_MAPPING[device.role][lag_intf["name"]]  # type: ignore[index]
            except KeyError:
                intf_role = "server"

            l2_mode = INTERFACE_L2_MODE_MAPPING.get(intf_role, "Access")

            description = lag_intf.get("description", "")

            untagged_vlan = None
            if l2_mode == "Access":
                untagged_vlan = store.get(kind=InfraVLAN, key=f"{site.name}_server")

            lag = await client.create(
                branch=branch,
                kind=InfraLagInterfaceL2,
                device={"id": obj.id, "is_protected": True},
                name=lag_intf["name"],
                description=description,
                speed=10000,
                enabled=True,
                l2_mode=l2_mode,
                untagged_vlan=untagged_vlan,
                status={"value": ACTIVE_STATUS, "owner": group_ops.id},
                role={"value": intf_role, "source": account_pop.id},
                lacp=lag_intf["lacp"],
            )

            await lag.save()

            store.set(key=f"{device_name}-lagl2-{lag_intf['name']}", node=lag)

            members = [
                store.get(key=f"{device_name}-l2-{member}", raise_when_missing=True).id
                for member in lag_intf["members"]
            ]
            await lag.add_relationships(relation_to_update="members", related_nodes=members)

    await generate_site_mlag_domain(client=client, log=log, branch=branch, site=site)

    # --------------------------------------------------
    # Connect both devices within the Site together with 2 interfaces
    # --------------------------------------------------
    for idx in range(2):
        intf1_l3 = store.get(kind=InfraInterfaceL3, key=f"{site.name}-edge1-l3-{idx}")
        intf2_l3 = store.get(kind=InfraInterfaceL3, key=f"{site.name}-edge2-l3-{idx}")

        intf1_l3.description.value = f"Connected to {site.name}-edge2 {intf2_l3.name.value}"
        intf1_l3.connected_endpoint = intf2_l3  # type: ignore[assignment]
        await intf1_l3.save()

        intf2_l3.description.value = f"Connected to {site.name}-edge1 {intf1_l3.name.value}"
        await intf2_l3.save()

        log.info(
            f" - Connected '{site.name}-edge1::{intf1_l3.name.value}' <> '{site.name}-edge2::{intf2_l3.name.value}'"
        )

    # --------------------------------------------------
    # Connect both leaf devices within a Site together with the 2 peer interfaces
    # --------------------------------------------------
    for idx in range(2):
        intf1_l2 = store.get(kind=InfraInterfaceL2, key=f"{site.name}-leaf1-l2-Ethernet{idx + 1}")
        intf2_l2 = store.get(kind=InfraInterfaceL2, key=f"{site.name}-leaf2-l2-Ethernet{idx + 1}")

        intf1_l2.description.value = f"Connected to {site.name}-leaf2 {intf2_l2.name.value}"
        intf1_l2.connected_endpoint = intf2_l2  # type: ignore[assignment]
        await intf1_l2.save()

        intf2_l2.description.value = f"Connected to {site.name}-leaf1 {intf1_l2.name.value}"
        await intf2_l2.save()

        log.info(
            f" - Connected '{site.name}-leaf1::{intf1_l2.name.value}' <> '{site.name}-leaf2::{intf2_l2.name.value}'"
        )

    # --------------------------------------------------
    # Update all the group we may have touched during the site creation
    # --------------------------------------------------

    if group_edge_router_members:
        group_edge_router = store.get(kind=CoreStandardGroup, key="edge_router")
        await group_edge_router.add_relationships(relation_to_update="members", related_nodes=group_edge_router_members)

    if group_core_router_members:
        group_core_router = store.get(kind=CoreStandardGroup, key="core_router")
        await group_core_router.add_relationships(relation_to_update="members", related_nodes=group_core_router_members)

    if group_cisco_devices_members:
        group_cisco_devices = store.get(kind=CoreStandardGroup, key="cisco_devices")
        await group_cisco_devices.add_relationships(
            relation_to_update="members", related_nodes=group_cisco_devices_members
        )
    if group_arista_devices_members:
        group_arista_devices = store.get(kind=CoreStandardGroup, key="arista_devices")
        await group_arista_devices.add_relationships(
            relation_to_update="members", related_nodes=group_arista_devices_members
        )

    if group_upstream_interfaces_members:
        group_upstream_interfaces = store.get(kind=CoreStandardGroup, key="upstream_interfaces")
        await group_upstream_interfaces.add_relationships(
            relation_to_update="members", related_nodes=group_upstream_interfaces_members
        )

    if group_backbone_interfaces_members:
        group_backbone_interfaces = store.get(kind=CoreStandardGroup, key="backbone_interfaces")
        await group_backbone_interfaces.add_relationships(
            relation_to_update="members", related_nodes=group_backbone_interfaces_members
        )

    # --------------------------------------------------
    # Create iBGP Sessions within the Site
    # --------------------------------------------------
    for idx in range(2):
        if idx == 0:
            device1 = f"{site.name}-{DEVICES[0].name}"
            device2 = f"{site.name}-{DEVICES[1].name}"
        elif idx == 1:
            device1 = f"{site.name}-{DEVICES[1].name}"
            device2 = f"{site.name}-{DEVICES[0].name}"

        peer_group_name = "POP_INTERNAL"

        loopback1 = store.get(key=f"{device1}-loopback", kind=InfraInterfaceL3, raise_when_missing=True)
        loopback2 = store.get(key=f"{device2}-loopback", kind=InfraInterfaceL3, raise_when_missing=True)

        obj = await client.create(
            branch=branch,
            kind=InfraBGPSession,
            type="INTERNAL",
            local_as=internal_as.id,
            local_ip=loopback1.id,
            remote_as=internal_as.id,
            remote_ip=loopback2.id,
            peer_group=store.get(key=peer_group_name, raise_when_missing=True).id,
            device=store.get(kind=InfraDevice, key=device1, raise_when_missing=True).id,
            status=ACTIVE_STATUS,
            role=BACKBONE_ROLE,
        )
        await obj.save()

        log.info(
            f" - Created BGP Session '{device1}' >> '{device2}': '{peer_group_name}' '{loopback1.address.value}' >> '{loopback2.address.value}'"
        )

    return site.name


async def branch_scenario_add_upstream(
    client: InfrahubClient, log: logging.Logger, site_name: str, external_pool: CoreNode
) -> None:
    """
    Create a new branch and Add a new upstream link with GTT on the edge1 device of the given site.
    """
    log.info("Create a new branch and Add a new upstream link with GTT on the edge1 device of the given site")
    device_name = f"{site_name}-edge1"

    new_branch_name = f"{site_name}-add-upstream"
    await client.branch.create(
        branch_name=new_branch_name, sync_with_git=False, description=f"Add a new Upstream link in {site_name}"
    )
    log.info(f"- Creating branch: {new_branch_name!r}")
    # Querying the object for now, need to pull from the store instead
    site = await client.get(branch=new_branch_name, kind=LocationSite, name__value=site_name)
    device = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device_name)
    gtt_organization = await client.get(
        branch=new_branch_name, kind=OrganizationProvider, name__value="GTT Communications"
    )

    role_spare = "spare"

    intfs = await client.filters(
        branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device.id], role__value=role_spare
    )
    intf = intfs[0]
    log.info(f" - Adding new Upstream on '{device_name}::{intf.name.value}'")

    # Allocate a new subnet and calculate new IP Addresses
    subnet = await client.allocate_next_ip_prefix(
        resource_pool=external_pool, identifier=device_name, branch=new_branch_name
    )
    subnet = cast(IpamIPPrefix, subnet)
    subnet_hosts = subnet.prefix.value.hosts()
    address = f"{str(next(subnet_hosts))}/29"
    peer_address = f"{str(next(subnet_hosts))}/29"

    peer_ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        address=peer_address,
    )
    await peer_ip.save()

    ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        interface={"id": intf.id},
        address={"value": address},
    )
    await ip.save()

    circuit_id_unique = str(uuid.UUID(int=abs(hash(f"{device_name}-upstream-{address}"))))[24:]
    circuit_id = f"DUFF-{circuit_id_unique}"

    circuit = await client.create(
        branch=new_branch_name,
        kind=InfraCircuit,
        circuit_id=circuit_id,
        vendor_id=f"{gtt_organization.name.value.upper()}-{UUIDT().short()}",
        provider=gtt_organization.id,
        status=ACTIVE_STATUS,
        role="upstream",
    )
    await circuit.save()
    log.info(f"  - Created {circuit._schema.kind} - {gtt_organization.name.value} [{circuit.vendor_id.value}]")

    endpoint1 = await client.create(
        branch=new_branch_name,
        kind=InfraCircuitEndpoint,
        site=site,
        circuit=circuit.id,
        connected_endpoint=intf.id,
    )
    await endpoint1.save()

    intf.description.value = f"Connected to {gtt_organization.name.value} via {circuit_id}"
    await intf.save()

    # Create BGP Session

    # Create Circuit
    # Create IP address
    # Change Role
    # Change description

    # peer_group_name = "UPSTREAM_DEFAULT"

    #     peer_as = store.get(kind="InfraAutonomousSystem", key=gtt_organization.name.value)
    #     bgp_session = await client.create(
    #         branch=branch,
    #         kind="InfraBGPSession",
    #         type="EXTERNAL",
    #         local_as=internal_as.id,
    #         local_ip=ip.id,
    #         remote_as=peer_as.id,
    #         remote_ip=peer_ip.id,
    #         peer_group=store.get(key=peer_group_name).id,
    #         device=store.get(key=device_name).id,
    #         status=ACTIVE_STATUS,
    #         role=store.get(kind="BuiltinRole", key=intf_role).id,
    #     )
    #     await bgp_session.save()

    #     log.info(
    #         f"Created BGP Session '{device_name}' >> '{gtt_organization.name.value}': '{peer_group_name}' '{ip.address.value}' >> '{peer_ip.address.value}'"
    #     )


async def branch_scenario_replace_ip_addresses(
    client: InfrahubClient, log: logging.Logger, site_name: str, interconnection_pool: CoreNode
) -> None:
    """
    Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site
    """
    device1_name = f"{site_name}-edge1"
    device2_name = f"{site_name}-edge2"

    new_branch_name = f"{site_name}-update-edge-ips"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Change the IP addresses between edge1 and edge2 in {site_name}",
    )
    log.info("Create a new Branch and Change the IP addresses between edge1 and edge2 on the selected site")
    log.info(f"- Creating branch: {new_branch_name!r}")

    new_peer_network = await client.allocate_next_ip_prefix(
        kind=IpamIPPrefix,
        resource_pool=interconnection_pool,
        identifier=f"{device1_name}__{device2_name}",
        branch=new_branch_name,
    )
    new_peer_network_hosts = new_peer_network.prefix.value.hosts()

    device1 = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device1_name)
    device2 = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device2_name)
    role_peer = "peer"

    peer_intfs_dev1 = sorted(
        await client.filters(
            branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device1.id], role__value=role_peer
        ),
        key=lambda x: x.name.value,
    )
    peer_intfs_dev2 = sorted(
        await client.filters(
            branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device2.id], role__value=role_peer
        ),
        key=lambda x: x.name.value,
    )

    # Querying the object for now, need to pull from the store instead
    peer_ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        interface={"id": peer_intfs_dev1[0].id},
        address=f"{str(next(new_peer_network_hosts))}/31",
    )
    await peer_ip.save()
    log.info(f" - Replaced {device1_name}-{peer_intfs_dev1[0].name.value} IP to {peer_ip.address.value}")

    ip = await client.create(
        branch=new_branch_name,
        kind=IpamIPAddress,
        interface={"id": peer_intfs_dev2[0].id},  # , "source": account_pop.id},
        address={"value": f"{str(next(new_peer_network_hosts))}/31"},  # , "source": account_pop.id},
    )
    await ip.save()
    log.info(f" - Replaced {device2_name}-{peer_intfs_dev2[0].name.value} IP to {ip.address.value}")


async def branch_scenario_remove_colt(client: InfrahubClient, log: logging.Logger, site_name: str) -> None:
    """
    Create a new Branch and Delete Colt Upstream Circuit
    """
    log.info("Create a new Branch and Delete Colt Upstream Circuit")
    new_branch_name = f"{site_name}-delete-upstream"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Delete upstream circuit with colt in {site_name}",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    # TODO need to update the role on the interface and need to delete the IP Address
    # for idx in range(1, 3):
    #     device_name = f"{site_name}-edge{idx}"
    #     device = await client.get(branch=new_branch_name, kind="InfraDevice", name__value=device_name)
    #     intf = await client.get(branch=new_branch_name, kind="InfraInterfaceL3", device__id=device.id, name__value="Ethernet5")

    # Delete circuits
    get_circuits_query = """
    query($site_name: String!) {
        InfraCircuitEndpoint(site__name__value: $site_name) {
            edges {
                node {
                    id
                    circuit {
                        node {
                            id
                            circuit_id {
                                value
                            }
                            provider {
                                node {
                                    name {
                                        value
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    circuits = await client.execute_graphql(
        branch_name=new_branch_name, query=get_circuits_query, variables={"site_name": site_name}
    )
    colt_circuits = [
        circuit
        for circuit in circuits["InfraCircuitEndpoint"]["edges"]
        if circuit["node"]["circuit"]["node"]["provider"]["node"]["name"]["value"] == "Colt Technology Services"
    ]

    for item in colt_circuits:
        circuit_id = item["node"]["circuit"]["node"]["circuit_id"]["value"]
        circuit_endpoint = await client.get(branch=new_branch_name, kind=InfraCircuitEndpoint, id=item["node"]["id"])
        await circuit_endpoint.delete()

        circuit = await client.get(branch=new_branch_name, kind=InfraCircuit, id=item["node"]["circuit"]["node"]["id"])
        await circuit.delete()
        log.info(f" - Deleted Colt Technology Services [{circuit_id}]")


async def branch_scenario_conflict_device(client: InfrahubClient, log: logging.Logger, site_name: str) -> None:
    """
    Create a new Branch and introduce some conflicts
    """
    log.info("Create a new Branch and introduce some conflicts")
    device1_name = f"{site_name}-edge1"
    f"{site_name}-edge2"

    new_branch_name = f"{site_name}-maintenance-conflict"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description=f"Put {device1_name} in maintenance mode",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    maintenance_status = "maintenance"
    provisioning_status = "provisioning"
    drained_status = "drained"

    # Update Device 1 Status both in the Branch and in Main
    device1_branch = await client.get(branch=new_branch_name, kind=InfraDevice, name__value=device1_name)

    device1_branch.status.value = maintenance_status
    await device1_branch.save()

    intf1_branch = await client.get(
        branch=new_branch_name, kind=InfraInterfaceL3, device__ids=[device1_branch.id], name__value="Ethernet1"
    )
    intf1_branch.enabled.value = False
    intf1_branch.status.value = drained_status
    await intf1_branch.save()

    device1_main = await client.get(kind=InfraDevice, name__value=device1_name)

    device1_main.status.value = provisioning_status
    await device1_main.save()

    intf1_main = await client.get(kind=InfraInterfaceL3, device__ids=[device1_branch.id], name__value="Ethernet1")
    intf1_main.enabled.value = False
    await intf1_main.save()


async def branch_scenario_conflict_platform(client: InfrahubClient, log: logging.Logger) -> None:
    """
    Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE
    """
    log.info("Create a new Branch and introduce some conflicts on the platforms for node ADD and DELETE")
    new_branch_name = "platform-conflict"
    await client.branch.create(
        branch_name=new_branch_name,
        sync_with_git=False,
        description="Add new platform",
    )
    log.info(f"- Creating branch: {new_branch_name!r}")

    # Create a new Platform object with the same name, both in the branch and in main
    platform1_branch = await client.create(
        branch=new_branch_name, kind=InfraPlatform, name="Cisco IOS XR", netmiko_device_type="cisco_xr"
    )
    await platform1_branch.save()
    platform1_main = await client.create(kind=InfraPlatform, name="Cisco IOS XR", netmiko_device_type="cisco_xr")
    await platform1_main.save()

    # Delete an existing Platform object on both in the Branch and in Main
    platform2_branch = await client.get(branch=new_branch_name, kind=InfraPlatform, name__value="Cisco NXOS SSH")
    await platform2_branch.delete()
    platform2_main = await client.get(kind=InfraPlatform, name__value="Cisco NXOS SSH")
    await platform2_main.delete()

    # Delete an existing Platform object in the branch and update it in main
    platform3_branch = await client.get(branch=new_branch_name, kind=InfraPlatform, name__value="Juniper JunOS")
    await platform3_branch.delete()
    platform3_main = await client.get(kind=InfraPlatform, name__value="Juniper JunOS")
    platform3_main.nornir_platform.value = "juniper_junos"
    await platform3_main.save()


async def generate_continents_countries(client: InfrahubClient, log: logging.Logger, branch: str) -> None:
    continent_batch = await client.create_batch()
    country_batch = await client.create_batch()

    for continent, countries in CONTINENT_COUNTRIES.items():
        continent_obj = await client.create(branch=branch, kind="LocationContinent", data={"name": continent})
        continent_batch.add(task=continent_obj.save, node=continent_obj)
        store.set(key=continent, node=continent_obj)

        for country in countries:
            country_obj = await client.create(
                branch=branch, kind="LocationCountry", data={"name": country, "parent": continent_obj}
            )
            country_batch.add(task=country_obj.save, node=country_obj)

            store.set(key=country, node=country_obj)

    async for node, _ in continent_batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    async for node, _ in country_batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    log.info("Created continents and countries")


async def prepare_accounts(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    # FIXME: For some reason this part doesn't work
    # groups = await client.filters(branch=branch, kind="CoreUserGroup", name__value="Administrators")
    # store.set(key=groups[0].name, node=groups[0])

    for account in ACCOUNTS:
        data = account.model_dump()
        # data["member_of_groups"] = groups

        obj = await client.create(branch=branch, kind="CoreAccount", data=data)
        batch.add(task=obj.save, node=obj)
        store.set(key=account.name, node=obj)


async def prepare_asns(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    account_chloe = store.get("Chloe O'Brian", kind=CoreAccount, raise_when_missing=True)
    account_crm = store.get("CRM Synchronization", kind=CoreAccount, raise_when_missing=True)
    organizations_dict = {org.name: org.type for org in ORGANIZATIONS}
    for asn in ASNS:
        organization_type = organizations_dict.get(asn.organization, None)
        asn_name = f"AS{asn.asn}"
        data_asn = {
            "name": {"value": asn.name, "source": account_crm.id, "owner": account_chloe.id},
            "asn": {"value": asn.asn, "source": account_crm.id, "owner": account_chloe.id},
        }
        if organization_type:
            data_asn["description"] = {
                "value": f"{asn_name} for {asn.organization}",
                "source": account_crm.id,
                "owner": account_chloe.id,
            }
            data_asn["organization"] = {
                "id": store.get(
                    kind=f"Organization{organization_type.title()}", raise_when_missing=True, key=asn.organization
                ).id,
                "source": account_crm.id,
            }
        else:
            data_asn["description"] = {"value": f"{asn_name}", "source": account_crm.id, "owner": account_chloe.id}
        obj = await client.create(branch=branch, kind="InfraAutonomousSystem", data=data_asn)
        batch.add(task=obj.save, node=obj)
        store.set(key=asn.organization, node=obj)


async def prepare_bgp_peer_groups(
    client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch
) -> None:
    account_pop = store.get("pop-builder", kind=CoreAccount, raise_when_missing=True)

    log.info("Creating BGP Peer Groups")
    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        local_as_id = None
        local_as = store.get(kind="InfraAutonomousSystem", key=peer_group.local_as, raise_when_missing=False)
        remote_as = (
            store.get(kind="InfraAutonomousSystem", key=peer_group.remote_as, raise_when_missing=False)
            if peer_group.remote_as
            else None
        )
        if remote_as:
            remote_as_id = remote_as.id
        if local_as:
            local_as_id = local_as.id

        obj = await client.create(
            branch=branch,
            kind="InfraBGPPeerGroup",
            name={"value": peer_group.name, "source": account_pop.id},
            import_policies={"value": peer_group.import_policies, "source": account_pop.id},
            export_policies={"value": peer_group.export_policies, "source": account_pop.id},
            local_as={"id": local_as_id},
            remote_as={"id": remote_as_id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=peer_group.name, node=obj)


async def prepare_groups(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    for group in GROUPS:
        obj = await client.create(branch=branch, kind=CoreStandardGroup, data=group.model_dump())

        batch.add(task=obj.save, node=obj)
        store.set(key=group.name, node=obj)


async def prepare_interface_profiles(
    client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch
) -> None:
    for intf_profile in INTERFACE_PROFILES:
        data_profile = {
            "profile_name": {"value": intf_profile.name},
            "mtu": {"value": intf_profile.mtu},
        }
        profile = await client.create(branch=branch, kind=intf_profile.profile_kind, data=data_profile)
        batch.add(task=profile.save, node=profile)
        store.set(key=intf_profile.name, node=profile)


async def prepare_organizations(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    for org in ORGANIZATIONS:
        data_org = {
            "name": {"value": org.name, "is_protected": True},
        }
        obj = await client.create(branch=branch, kind=org.kind, data=data_org)
        batch.add(task=obj.save, node=obj)
        store.set(key=org.name, node=obj)


async def prepare_platforms(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    for platform in PLATFORMS:
        obj = await client.create(
            branch=branch,
            kind=InfraPlatform,
            data=platform.model_dump(),
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=platform.name, node=obj)


async def prepare_tags(client: InfrahubClient, log: logging.Logger, branch: str, batch: InfrahubBatch) -> None:
    account_pop = store.get("pop-builder", kind=CoreAccount, raise_when_missing=True)

    log.info("Creating Tags")
    for tag in TAGS:
        obj = await client.create(branch=branch, kind="BuiltinTag", name={"value": tag, "source": account_pop.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(
    client: InfrahubClient,
    log: logging.Logger,
    branch: str,
    profile: str = None,
    num_sites: int = None,
    num_device_per_site: int = None,
    has_bgp_mesh: str = None,
    has_branch: str = None,
) -> None:
    # Create timer to keep track of time elapsed
    start: float = time.time()

    # ------------------------------------------
    # Config
    # ------------------------------------------
    # Create an instance of the global configuration
    config = GlobalConfig()

    # Translate str to bool
    bool_has_bgp_mesh: bool = None
    if has_bgp_mesh is not None:
        bool_has_bgp_mesh = translate_str_to_bool("has_bgp_mesh", has_bgp_mesh)

    bool_has_branch: bool = None
    if has_branch is not None:
        bool_has_branch = translate_str_to_bool("has_branch", has_branch)

    # Load args into the config
    try:
        config.load_config(profile, num_sites, num_device_per_site, bool_has_bgp_mesh, bool_has_branch)
    except ConfigError as ex:
        log.fatal(ex)
        return False  # FIXME: What should I return here for the script to fail properly

    # Print config
    log.info(f"Loading data with {config}")

    # ------------------------------------------
    # Create Continents, Countries
    # ------------------------------------------
    num_sites = int(config.num_sites)
    log.info("Creating Infrastructure Data")

    await generate_continents_countries(client=client, log=log, branch=branch)

    # ------------------------------------------
    # Create User Accounts, Groups, Organizations & Platforms
    # ------------------------------------------
    log.info("Creating User Accounts, Groups & Organizations & Platforms")

    batch = await client.create_batch()
    await prepare_accounts(client=client, log=log, branch=branch, batch=batch)
    await prepare_groups(client=client, log=log, branch=branch, batch=batch)
    await prepare_platforms(client=client, log=log, branch=branch, batch=batch)
    await prepare_organizations(client=client, log=log, branch=branch, batch=batch)
    await prepare_interface_profiles(client=client, log=log, branch=branch, batch=batch)

    async for node, _ in batch.execute():
        if node._schema.namespace == "Profile":
            log.info(f"- Created {node._schema.kind} - {node.profile_name.value}")
        else:
            log.info(f"- Created {node._schema.kind} - {node.name.value}")

    account_pop = store.get("pop-builder", kind=CoreAccount, raise_when_missing=True)

    batch = await client.create_batch()
    await prepare_asns(client=client, log=log, branch=branch, batch=batch)
    await prepare_tags(client=client, log=log, branch=branch, batch=batch)

    async for node, _ in batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    batch = await client.create_batch()
    await prepare_bgp_peer_groups(client=client, log=log, branch=branch, batch=batch)
    async for node, _ in batch.execute():
        log.info(f"- Created {node._schema.kind} - {node.name.value}")

    # ------------------------------------------
    # Create IP prefixes
    # ------------------------------------------
    default_ip_namespace = await client.get(kind=IpamNamespace, name__value="default")

    log.info("Creating IP Prefixes")

    log.info("Creating IP Core Supernet and Pool")
    supernet_prefix = await client.create(
        branch=branch, kind=IpamIPPrefix, prefix=str(NETWORKS_SUPERNET), member_type="prefix"
    )
    await supernet_prefix.save()
    supernet_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Internal networks pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=16,
        ip_namespace=default_ip_namespace,
        resources=[supernet_prefix],
        branch=branch,
    )
    await supernet_pool.save()

    log.info("Creating IP Loopback Prefix and Pool")
    loopback_prefix = await client.allocate_next_ip_prefix(
        resource_pool=supernet_pool, member_type="address", branch=branch
    )
    loopback_pool = await client.create(
        kind=CoreIPAddressPool,
        name="Loopbacks pool",
        default_address_type="IpamIPAddress",
        default_prefix_length=32,
        ip_namespace=default_ip_namespace,
        resources=[loopback_prefix],
        branch=branch,
    )
    await loopback_pool.save()

    log.info("Creating IP Interconnection Prefix and Pool")
    interconnection_prefix = await client.allocate_next_ip_prefix(
        kind=IpamIPPrefix, resource_pool=supernet_pool, branch=branch
    )
    interconnection_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Interconnections pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=31,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[interconnection_prefix],
        branch=branch,
    )
    await interconnection_pool.save()
    store.set(key="interconnection_pool", node=interconnection_pool)

    # Allocate an empty prefix
    await client.allocate_next_ip_prefix(resource_pool=supernet_pool, branch=branch)

    log.info("Creating IP Management Prefix and Pool")
    management_prefix = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(MANAGEMENT_NETWORKS), member_type="address"
    )
    await management_prefix.save()
    management_pool = await client.create(
        kind=CoreIPAddressPool,
        name="Management addresses pool",
        default_address_type="IpamIPAddress",
        default_prefix_length=28,
        ip_namespace=default_ip_namespace,
        resources=[management_prefix],
        branch=branch,
    )
    await management_pool.save()

    log.info("Creating IP External Supernet and Pool")
    external_supernet = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_POOL_EXTERNAL_SUPERNET), member_type="prefix"
    )
    await external_supernet.save()
    external_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="External prefixes pool",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=29,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[external_supernet],
        branch=branch,
    )
    await external_pool.save()

    log.info("Creating IPv6 Core Supernet and Pool")
    ipv6_supernet_prefix = await client.create(
        branch=branch, kind="IpamIPPrefix", prefix=str(NETWORKS_SUPERNET_IPV6), member_type="prefix"
    )
    await ipv6_supernet_prefix.save()
    ipv6_supernet_pool = await client.create(
        kind=CoreIPPrefixPool,
        name="Internal networks pool (IPv6)",
        default_prefix_type="IpamIPPrefix",
        default_prefix_length=120,
        default_member_type="address",
        ip_namespace=default_ip_namespace,
        resources=[ipv6_supernet_prefix],
        branch=branch,
    )
    await ipv6_supernet_pool.save()

    # ------------------------------------------
    # Create Pool IPv6 prefixes
    # ------------------------------------------
    log.info("Creating pool IPv6 Prefixes and IPs")
    ipv6_internal_networks: list[IpamIPPrefix] = [
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
        await client.allocate_next_ip_prefix(resource_pool=ipv6_supernet_pool, kind=IpamIPPrefix, branch=branch),
    ]

    log.info("IP Prefixes Creation Completed")

    # ------------------------------------------
    # Create IPv6 IP from IPv6 Prefix pool
    # ------------------------------------------
    ipv6_addresses = []
    for index, network in enumerate(ipv6_internal_networks[:4]):
        multiplier = index + 1
        host_list = list(network.prefix.value.hosts())
        number_of_hosts = min(multiplier * 17, len(host_list))
        ipv6_addresses.extend(host_list[:number_of_hosts])

    batch = await client.create_batch()
    for ipv6_addr in ipv6_addresses:
        obj = await client.create(
            branch=branch, kind=IpamIPAddress, address={"value": ipv6_addr, "source": account_pop.id}
        )
        batch.add(task=obj.save, node=obj)

    async for _, response in batch.execute():
        log.debug(f"{response} - Creation Completed")

    log.info("IPv6 Address Creation Completed")

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Creating Site and associated objects (Device, Circuit, BGP Sessions)")
    sites = site_generator(nbr_site=num_sites)
    for site in sites:
        response = await generate_site(
            client=client,
            log=log,
            branch=branch,
            site=site,
            interconnection_pool=interconnection_pool,
            loopback_pool=loopback_pool,
            management_pool=management_pool,
            external_pool=external_pool,
        )
        log.info(f"{response} - Creation Completed")

    await apply_interface_profiles(
        client=client,
        branch=branch,
        log=log,
    )

    await create_bgp_mesh(client=client, branch=branch, log=log, sites=sites)

    await create_backbone_connectivity(client=client, branch=branch, log=log, num_sites=num_sites)

    # --------------------------------------------------
    # Create some changes in additional branches
    #  Scenario 1 - Add a Peering
    #  Scenario 2 - Change the IP Address between 2 edges
    #  Scenario 3 - Delete a Circuit + Peering
    #  Scenario 4 - Create some Relationship One and Attribute conflicts on a device
    #  Scenario 5 - Create some Node ADD and DELETE conflicts on some platform objects
    # --------------------------------------------------
    if branch == "main":
        await branch_scenario_add_upstream(site_name=sites[1].name, client=client, log=log, external_pool=external_pool)
        await branch_scenario_replace_ip_addresses(
            site_name=sites[2].name, client=client, log=log, interconnection_pool=interconnection_pool
        )
        await branch_scenario_remove_colt(site_name=sites[0].name, client=client, log=log)
        await branch_scenario_conflict_device(site_name=sites[3].name, client=client, log=log)
        await branch_scenario_conflict_platform(client=client, log=log)

    # Stop the timer and display elapsed time
    end: float = time.time()
    log.info(f"Data loaded in {round(end - start)}s")
