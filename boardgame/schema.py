"""Small explicit JSON Schema subset used by our published action contracts."""

from boardgame.core import require


def obj(properties, required=()):
    return dict(
        type="object",
        properties=properties,
        required=list(required),
        additionalProperties=False,
    )


def arr(items, max_items=100):
    return dict(type="array", items=items, maxItems=max_items)


def enum(*values):
    return {"enum": list(values)}


STRING = {"type": "string", "minLength": 1, "maxLength": 200}
INT = {"type": "integer"}
BOOL = {"type": "boolean"}
POINT = dict(
    type="array",
    items=dict(type="integer", minimum=0, maximum=29),
    minItems=2,
    maxItems=2,
)


def validate(value, schema, path="action"):
    if "enum" in schema:
        require(
            value in schema["enum"],
            f"{path}: expected one of {schema['enum']}",
            "invalid_parameters",
        )
    typ = schema.get("type")
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "boolean": type(value) is bool,
    }
    if typ:
        require(valid[typ], f"{path}: expected {typ}", "invalid_parameters")
    if typ == "object":
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        require(
            all(k in value for k in schema.get("required", [])),
            f"{path}: missing required fields {schema.get('required', [])}",
            "invalid_parameters",
        )
        for k, v in value.items():
            require(
                k in props or additional is not False,
                f"{path}: unknown field {k}",
                "invalid_parameters",
            )
            if k in props:
                validate(v, props[k], path + "." + k)
            elif isinstance(additional, dict):
                validate(v, additional, path + "." + k)
    if typ == "array":
        require(
            schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 1000),
            f"{path}: invalid array length",
            "invalid_parameters",
        )
        for i, v in enumerate(value):
            validate(v, schema.get("items", {}), f"{path}[{i}]")
    if typ == "string":
        require(
            schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 10000),
            f"{path}: invalid text length",
            "invalid_parameters",
        )
    if typ == "integer":
        require(
            schema.get("minimum", -(10**18)) <= value <= schema.get("maximum", 10**18),
            f"{path}: integer out of range",
            "invalid_parameters",
        )
