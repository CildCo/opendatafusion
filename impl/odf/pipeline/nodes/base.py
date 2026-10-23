from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    type: str
    nullable: bool = True


class NodeExecutor:
    def schema(self, inputs, config):
        raise NotImplementedError

    def run(self, inputs, config, ctx):
        raise NotImplementedError


_REGISTRY = {}


def register_node(type_):
    def deco(cls):
        _REGISTRY[type_] = cls
        return cls
    return deco


def get_node(type_):
    if type_ not in _REGISTRY:
        raise ValueError("unknown node type: %s" % type_)
    return _REGISTRY[type_]


@dataclass
class RunContext:
    session: object
    cursors: dict = field(default_factory=dict)
    new_cursors: dict = field(default_factory=dict)
    batch: int = 1000
    preview: bool = False
    current_node: str | None = None
    timeout_s: float | None = None
    stats: dict = field(default_factory=dict)
    cursor_override: dict = field(default_factory=dict)
    until_cursor: str | None = None
    persist_cursor: bool = True
    exhausted_nodes: set = field(default_factory=set)
