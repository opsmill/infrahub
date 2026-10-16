from __future__ import annotations

from tests.constants import TestKind

# The car is the group member; the tag stands in for an artifact or generator definition. The impact
# mapping reads only the subscriber's id and typename, so a plain kind keeps the fixture free of the
# transformation and repository wiring a real definition would demand.
SUBSCRIBER_KIND = TestKind.TAG
