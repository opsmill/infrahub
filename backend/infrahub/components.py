from enum import IntFlag


class ComponentType(IntFlag):
    NONE = 0
    API_SERVER = 1
    GIT_AGENT = 2
