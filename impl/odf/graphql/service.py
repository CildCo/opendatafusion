import re

from graphql import (GraphQLArgument, GraphQLBoolean, GraphQLField,
                     GraphQLFloat, GraphQLInt, GraphQLList, GraphQLNonNull,
                     GraphQLObjectType, GraphQLScalarType, GraphQLSchema,
                     GraphQLString, GraphQLError, graphql_sync,
                     print_schema, value_from_ast_untyped)

from odf.models import Asset, AssetVersion

_FIELD = re.compile(r"[^_0-9A-Za-z]")


def _json_value(value):
    return value


JSON = GraphQLScalarType(
    name="JSON", description="Arbitrary JSON value",
    serialize=_json_value, parse_value=_json_value,
    parse_literal=value_from_ast_untyped)


def _field_name(key):
    name = _FIELD.sub("_", key or "api")
    if not name or name[0].isdigit():
        name = "api_" + name
    return name


def _arg_type(kind):
    kind = (kind or "string").lower()
    if kind == "number":
        return GraphQLFloat
    if kind == "bool":
        return GraphQLBoolean
    if kind == "integer":
        return GraphQLInt
    return GraphQLString


def _apis(session, project_id):
    rows = (session.query(Asset)
            .filter(Asset.project_id == project_id, Asset.type == "api",
                    Asset.enabled.is_(True),
                    Asset.published_version_id.isnot(None))
            .order_by(Asset.id).all())
    out = []
    used = {}
    for asset in rows:
        name = _field_name(asset.key)
        if name in used:
            name = "%s_%d" % (name, asset.id)
        used[name] = asset
        out.append((name, asset))
    return out


def _result_type():
    return GraphQLObjectType("ApiResult", {
        "total": GraphQLField(GraphQLInt),
        "rows": GraphQLField(GraphQLList(JSON)),
    })


def build_schema(session, project_id):
    result_type = _result_type()
    fields = {}
    for name, asset in _apis(session, project_id):
        version = session.get(AssetVersion, asset.published_version_id)
        content = version.content_json if version else {}
        args = {}
        for param in content.get("params") or []:
            if not isinstance(param, dict) or not param.get("name"):
                continue
            arg_name = _FIELD.sub("_", param["name"])
            if not arg_name or arg_name[0].isdigit():
                continue
            kind = _arg_type(param.get("type"))
            if param.get("required"):
                kind = GraphQLNonNull(kind)
            args[arg_name] = GraphQLArgument(kind)
        fields[name] = GraphQLField(
            result_type, args=args,
            resolve=_resolver(asset.id, content, name),
            description="%s (%s)" % (asset.name, asset.key))
    query = GraphQLObjectType("Query", fields or {
        "_empty": GraphQLField(GraphQLBoolean,
                               resolve=lambda *_: True)})
    return GraphQLSchema(query=query)


def _resolver(asset_id, content, name):
    def resolve(_root, info, **kwargs):
        session = info.context["session"]
        asset = session.get(Asset, asset_id)
        if not asset or not asset.enabled or not asset.published_version_id:
            raise GraphQLError("API is not available")
        from odf.apistudio.service import ApiError, run_content
        try:
            result = run_content(session, asset, content, kwargs,
                                 role="viewer")
        except ApiError:
            raise GraphQLError("query failed")
        except Exception:
            raise GraphQLError("query failed")
        return {"total": result["row_count"], "rows": result["rows"]}
    return resolve


def execute(session, project_id, query, variables=None, operation_name=None):
    schema = build_schema(session, project_id)
    return graphql_sync(schema, query, context_value={"session": session},
                        variable_values=variables or {},
                        operation_name=operation_name)


def sdl(session, project_id):
    return print_schema(build_schema(session, project_id))


def example(session, project_id):
    for name, asset in _apis(session, project_id):
        version = session.get(AssetVersion, asset.published_version_id)
        content = version.content_json if version else {}
        arg_names = [p.get("name") for p in content.get("params") or []
                     if isinstance(p, dict) and p.get("name")]
        args = ""
        if arg_names:
            args = "(%s)" % ", ".join(
                "%s: null" % a for a in arg_names)
        return "query {\n  %s%s {\n    total\n    rows\n  }\n}" % (
            name, args)
    return "query {\n  _empty\n}"
