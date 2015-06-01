import re
import types

from numbers import Number


class QueryError(Exception):
    pass


class Query(object):
    def __init__(self, definition):
        self._definition = definition

    def match(self, entry):
        return self._match(self._definition, entry)

    def _match(self, condition, entry):
        if isinstance(condition, dict):
            return all(
                self._process_condition(sub_operator, sub_condition, entry)
                for sub_operator, sub_condition in condition.items()
            )
        else:
            if isinstance(entry, list):
                return condition in entry
            else:
                return condition == entry

    def _extract(self, entry, path):
        if not path:
            return entry
        if entry is None:
            return entry
        if isinstance(entry, list):
            try:
                index = int(path[0])
                return self._extract(entry[index], path[1:])
            except ValueError:
                return [self._extract(item, path) for item in entry]
        elif path[0] in entry:
            return self._extract(entry[path[0]], path[1:])
        else:
            return entry

    def _process_condition(self, operator, condition, entry):
        if operator.startswith("$"):
            try:
                op = getattr(self, "_" + operator[1:])

                # Added to support queries on lists of dicts
                if isinstance(entry, list) and not Query._is_array_op(operator):
                    return any(op(condition, en) for en in entry)
                else:
                    return op(condition, entry)
            except AttributeError:
                raise QueryError("{!r} operator isn't supported".format(operator))
        else:
            if isinstance(condition, dict) and "$exists" in condition:
                if condition["$exists"] != (operator in entry):
                    return False

            extracted_data = self._extract(
                entry,
                operator.split(".")
            )

            return self._match(condition, extracted_data)

    ##################
    # Common operators
    ##################

    def _not_implemented(self, *args):
        raise NotImplementedError

    def _noop(self, *args):
        return True

    ######################
    # Comparison operators
    ######################

    def _gt(self, condition, entry):
        return isinstance(entry, Number) and entry > condition

    def _gte(self, condition, entry):
        return isinstance(entry, Number) and entry >= condition

    def _in(self, condition, entry):
        return entry in condition

    def _lt(self, condition, entry):
        return isinstance(entry, Number) and entry < condition

    def _lte(self, condition, entry):
        return isinstance(entry, Number) and entry <= condition

    def _ne(self, condition, entry):
        return entry != condition

    def _nin(self, condition, entry):
        return entry not in condition

    ###################
    # Logical operators
    ###################

    def _and(self, condition, entry):
        if isinstance(condition, list):
            return all(
                self._match(sub_condition, entry)
                for sub_condition in condition
            )
        raise QueryError(
            "$and has been attributed incorrect argument {!r}".format(
                condition
            )
        )

    def _nor(self, condition, entry):
        if isinstance(condition, list):
            return all(
                not self._match(sub_condition, entry)
                for sub_condition in condition
            )
        raise QueryError(
            "$nor has been attributed incorrect argument {!r}".format(
                condition
            )
        )

    def _not(self, condition, entry):
        return not self._match(condition, entry)

    def _or(self, condition, entry):
        if isinstance(condition, list):
            return any(
                self._match(sub_condition, entry)
                for sub_condition in condition
            )
        raise QueryError(
            "$nor has been attributed incorrect argument {!r}".format(
                condition
            )
        )

    ###################
    # Element operators
    ###################

    def _type(self, condition, entry):
        # TODO: further validation to ensure the right type
        # rather than just checking
        bson_type = {
            1: float,
            2: str,
            3: dict,
            4: list,
            5: bytearray,
            7: str,  # object id (uuid)
            8: bool,
            9: str,  # date (UTC datetime)
            10: types.NoneType,
            11: str,  # regex,
            13: str,  # Javascript
            15: str,  # JavaScript (with scope)
            16: int,  # 32-bit integer
            17: int,  # Timestamp
            18: int   # 64-bit integer
        }

        if condition not in bson_type:
            raise QueryError(
                "$type has been used with unknown type {!r}".format(condition))

        return type(entry) == bson_type.get(condition)

    _exists = _noop

    ######################
    # Evaluation operators
    ######################

    def _mod(self, condition, entry):
        return entry % condition[0] == condition[1]

    def _regex(self, condition, entry):
        if type(entry) != str:
            return False
        try:
            regex = re.match(
                "\A/(.+)/([imsx]{,4})\Z",
                condition,
                flags=re.DOTALL
            )
        except TypeError:
            raise QueryError(
                "{!r} is not a regular expression "
                "and should be a string".format(condition))

        if regex:
            flags = 0
            options = regex.group(2)
            for option in options:
                flags |= getattr(re, option.upper())
            try:
                match = re.search(regex.group(1), entry, flags=flags)
            except Exception as error:
                raise QueryError(
                    "{!r} failed to execute with error {!r}".format(
                        condition, error))
            return bool(match)
        else:
            raise QueryError(
                "{!r} is not using a known regular expression syntax".format(
                    condition
                )
            )

    _options = _text = _where = _not_implemented

    #################
    # Array operators
    #################

    @classmethod
    def _is_array_op(cls, op):
        return op in ['$all', '$elemMatch', '$size']

    def _all(self, condition, entry):
        return all(
            self._match(item, entry)
            for item in condition
        )

    def _elemMatch(self, condition, entry):
        return any(
            all(
                self._process_condition(sub_operator, sub_condition, element)
                for sub_operator, sub_condition in condition.items()
            )
            for element in entry
        )

    def _size(self, condition, entry):
        if type(condition) != int:
            raise QueryError(
                "$size has been attributed incorrect argument {!r}".format(
                    condition
                )
            )

        if isinstance(entry, list):
            return len(entry) == condition

        return False

    ####################
    # Comments operators
    ####################

    _comment = _noop


