from odf.pipeline.schema import input_edges, topo_order, validate_dag


def test_valid_dag():
    c = {"nodes": [
        {"id": "s", "type": "source", "config": {}},
        {"id": "f", "type": "filter", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "s", "to": "f"}, {"from": "f", "to": "o"}]}
    assert validate_dag(c) == []
    assert topo_order(c) == ["s", "f", "o"]


def test_cycle_rejected():
    c = {"nodes": [
        {"id": "a", "type": "filter", "config": {}},
        {"id": "b", "type": "filter", "config": {}}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]}
    errs = validate_dag(c)
    assert any("环" in e["message"] for e in errs)


def test_missing_sink():
    c = {"nodes": [{"id": "s", "type": "source", "config": {}}], "edges": []}
    assert any(e["field"] == "sink" for e in validate_dag(c))


def test_malformed_nodes_and_edges_return_errors():
    c = {"nodes": [
        {"type": "source"},
        {"id": "s", "type": "source", "config": {}},
        "not-a-node"],
        "edges": [{"to": "s"}, "not-an-edge"]}
    errs = validate_dag(c)
    assert errs
    assert all(isinstance(e, dict) and e.get("message") for e in errs)


def test_disconnected_nodes_are_rejected():
    c = {"nodes": [
        {"id": "s", "type": "source", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": []}
    errs = validate_dag(c)
    assert any(e.get("node_id") == "o" and e["field"] == "connectivity"
               for e in errs)


def test_unimplemented_node_type_is_rejected():
    c = {"nodes": [
        {"id": "s", "type": "source", "config": {}},
        {"id": "w", "type": "window", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "s", "to": "w"}, {"from": "w", "to": "o"}]}
    assert any(e.get("node_id") == "w" and e["field"] == "type"
               for e in validate_dag(c))


def test_preview_mode_allows_unconnected_output():
    c = {"nodes": [
        {"id": "s", "type": "source", "config": {}},
        {"id": "f", "type": "filter", "config": {}}],
        "edges": [{"from": "s", "to": "f"}]}
    assert validate_dag(c, for_preview=True) == []


def test_join_requires_two_ports():
    c = {"nodes": [
        {"id": "a", "type": "source", "config": {}},
        {"id": "b", "type": "source", "config": {}},
        {"id": "j", "type": "join", "config": {"on": []}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "a", "to": "j", "to_port": "left"},
                  {"from": "b", "to": "j", "to_port": "right"},
                  {"from": "j", "to": "o"}]}
    assert validate_dag(c) == []
    assert input_edges(c, "j")[0]["from"] == "a"
    assert input_edges(c, "j")[1]["from"] == "b"


def test_join_duplicate_port_is_rejected():
    c = {"nodes": [
        {"id": "a", "type": "source", "config": {}},
        {"id": "b", "type": "source", "config": {}},
        {"id": "j", "type": "join", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "a", "to": "j", "to_port": "left"},
                  {"from": "b", "to": "j", "to_port": "left"},
                  {"from": "j", "to": "o"}]}
    assert any(e["field"] == "to_port" for e in validate_dag(c))


def test_explicit_right_infers_left_complement():
    c = {"nodes": [
        {"id": "a", "type": "source", "config": {}},
        {"id": "b", "type": "source", "config": {}},
        {"id": "j", "type": "join", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "b", "to": "j", "to_port": "right"},
                  {"from": "a", "to": "j"},
                  {"from": "j", "to": "o"}]}
    assert validate_dag(c) == []
    assert [e["from"] for e in input_edges(c, "j")] == ["a", "b"]
    assert [e["to_port"] for e in input_edges(c, "j")] == ["left", "right"]


def test_invalid_to_port_is_rejected():
    c = {"nodes": [
        {"id": "a", "type": "source", "config": {}},
        {"id": "b", "type": "source", "config": {}},
        {"id": "j", "type": "join", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "a", "to": "j", "to_port": "left"},
                  {"from": "b", "to": "j", "to_port": "middle"},
                  {"from": "j", "to": "o"}]}
    assert any(e["field"] == "to_port" for e in validate_dag(c))
