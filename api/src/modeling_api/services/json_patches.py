"""Apply the supported RFC 6902 operations before validating a task document."""

from copy import deepcopy

from modeling_api.core.errors import ApiError


def apply_json_patches(document, operations):
    result = deepcopy(document)
    try:
        for operation in operations:
            path, kind = operation.path, operation.op
            if not path:
                if kind == "remove":
                    raise ValueError()
                result = deepcopy(operation.value)
                continue
            if not path.startswith("/"):
                raise ValueError()
            keys = [key.replace("~1", "/").replace("~0", "~") for key in path[1:].split("/")]
            parent = result
            for key in keys[:-1]:
                parent = parent[int(key)] if isinstance(parent, list) else parent[key]
            key = keys[-1]
            if isinstance(parent, list):
                index = len(parent) if key == "-" and kind == "add" else int(key)
                if index < 0 or index > len(parent) or (kind != "add" and index == len(parent)):
                    raise ValueError()
                if kind == "add":
                    parent.insert(index, deepcopy(operation.value))
                elif kind == "remove":
                    parent.pop(index)
                else:
                    parent[index] = deepcopy(operation.value)
            elif isinstance(parent, dict):
                if kind != "add" and key not in parent:
                    raise ValueError()
                if kind == "remove":
                    del parent[key]
                else:
                    parent[key] = deepcopy(operation.value)
            else:
                raise ValueError()
        if not isinstance(result, dict):
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ApiError(422, "INVALID_TASK_EDIT", "An editing patch cannot be applied to this task state.") from error
    return result
