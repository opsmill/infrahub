from typing import Any, Dict, List, Union

import ujson

LoadedJson = Union[Dict[Any, Any], List[Any]]


def are_json_equal(left: str, right: str, order_matters: bool = True) -> bool:
    equality_checker = JsonEqualityChecker(order_matters=order_matters)
    return equality_checker.are_equal(left, right)


class JsonEqualityChecker:
    def __init__(self, order_matters: bool = True):
        self.order_matters = order_matters

    def are_equal(self, left: str, right: str) -> bool:
        if left == right:
            return True

        left_loaded = ujson.loads(left)
        right_loaded = ujson.loads(right)

        return self._is_equal(left_loaded, right_loaded)

    def _is_equal(self, left: LoadedJson, right: LoadedJson) -> bool:
        if not type(left) == type(right):
            return False

        if isinstance(left, list):
            if not len(left) == len(right):
                return False
            if self.order_matters:
                return all([self._is_equal(subleft, subright) for subleft, subright in zip(left, right)])
            for subleft in left:
                matches_right_element = False
                for subright in right:
                    if self._is_equal(subleft, subright):
                        matches_right_element = True
                        break
                if not matches_right_element:
                    return False
            return True

        elif isinstance(left, dict):
            if not len(left) == len(right):
                return False
            for left_key, left_value in left.items():
                if not self._is_equal(left_key, right[left_key]):
                    return False
                return True

        return left == right
