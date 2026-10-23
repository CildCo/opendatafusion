from collections import defaultdict, deque

NODE_TYPES = {"source", "filter", "select", "rename", "cast", "join",
              "aggregate", "union", "dedupe", "quality", "sink"}
TWO_INPUT = {"join", "union"}


def _err(node_id, field, message):
    return {"node_id": node_id, "field": field, "message": message}


def _expected_inputs(typ):
    if typ == "source":
        return 0
    if typ in TWO_INPUT:
        return 2
    return 1


def _shape(content):
    if not isinstance(content, dict):
        return {}, [], [_err(None, "content", "内容必须是对象")], False
    nodes = content.get("nodes") or []
    edges = content.get("edges") or []
    errs = []
    if not isinstance(nodes, list):
        return {}, [], [_err(None, "nodes", "nodes 必须是数组")], False
    if not isinstance(edges, list):
        return {}, [], [_err(None, "edges", "edges 必须是数组")], False
    by_id, duplicate = {}, False
    for n in nodes:
        if not isinstance(n, dict):
            errs.append(_err(None, "node", "节点必须是对象"))
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            errs.append(_err(None, "id", "节点 id 必须是非空字符串"))
            continue
        if nid in by_id:
            duplicate = True
            errs.append(_err(nid, "id", "节点 id 重复"))
            continue
        by_id[nid] = n
    valid_edges = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errs.append(_err(None, "edge", "第 %d 条边必须是对象" % (i + 1)))
            continue
        frm, to = e.get("from"), e.get("to")
        if not isinstance(frm, str) or not isinstance(to, str):
            errs.append(_err(None, "edge",
                             "第 %d 条边缺少 from/to" % (i + 1)))
            continue
        ok = True
        if frm not in by_id:
            errs.append(_err(frm, "edge", "悬挂起点"))
            ok = False
        if to not in by_id:
            errs.append(_err(to, "edge", "悬挂终点"))
            ok = False
        if ok:
            valid_edges.append(e)
    return by_id, valid_edges, errs, duplicate


def input_edges(content, node_id):
    nodes = {n.get("id"): n for n in (content.get("nodes") or [])
             if isinstance(n, dict)}
    typ = (nodes.get(node_id) or {}).get("type")
    edges = [e for e in (content.get("edges") or [])
             if isinstance(e, dict) and e.get("to") == node_id]
    if typ in TWO_INPUT:
        explicit = {e.get("to_port") for e in edges
                    if e.get("to_port") in ("left", "right")}
        for i, e in enumerate(edges):
            if e.get("to_port") not in ("left", "right"):
                if "left" not in explicit:
                    port = "left"
                elif "right" not in explicit:
                    port = "right"
                else:
                    port = "left" if i == 0 else "right"
                explicit.add(port)
                e = dict(e)
                e["to_port"] = port
                edges[i] = e
        edges.sort(key=lambda e: 0 if e["to_port"] == "left" else 1)
    return edges


def validate_dag(content, for_preview=False):
    by_id, edges, errs, duplicate = _shape(content)
    nodes = list(by_id.values())

    for n in nodes:
        if n.get("type") not in NODE_TYPES:
            errs.append(_err(n.get("id"), "type",
                             "未知节点类型 %s" % n.get("type")))
    if not any(n.get("type") == "source" for n in nodes):
        errs.append(_err(None, "source", "缺少 source 节点"))
    if not for_preview and not any(n.get("type") == "sink" for n in nodes):
        errs.append(_err(None, "sink", "缺少 sink 节点"))

    incoming = defaultdict(list)
    outdeg = defaultdict(int)
    for e in edges:
        incoming[e["to"]].append(e)
        outdeg[e["from"]] += 1

    for nid, n in by_id.items():
        typ = n.get("type")
        expected = _expected_inputs(typ)
        ins = incoming.get(nid, [])
        if typ == "source" and ins:
            errs.append(_err(nid, "connectivity", "source 不应有输入"))
        if typ != "source" and len(ins) != expected:
            errs.append(_err(nid, "connectivity",
                             "需要 %d 个输入，实际 %d" % (expected, len(ins))))
        if typ in TWO_INPUT:
            raw_ports = [e.get("to_port") for e in ins]
            if any(p is not None and p not in ("left", "right")
                   for p in raw_ports):
                errs.append(_err(nid, "to_port", "to_port 必须是 left/right"))
            elif len(ins) == 2:
                normalized = [e.get("to_port")
                              for e in input_edges(content, nid)]
                if sorted(normalized) != ["left", "right"]:
                    errs.append(_err(nid, "to_port", "left/right 端口重复"))
        if not for_preview and typ not in ("sink", None) and not outdeg[nid]:
            errs.append(_err(nid, "output", "输出未连接"))

    sources = [nid for nid, n in by_id.items() if n.get("type") == "source"]
    if sources:
        seen, q = set(sources), deque(sources)
        while q:
            cur = q.popleft()
            for e in edges:
                if e["from"] == cur and e["to"] not in seen:
                    seen.add(e["to"])
                    q.append(e["to"])
        for nid in by_id:
            if nid not in seen:
                errs.append(_err(nid, "connectivity", "无法从 source 到达"))

    if nodes and not duplicate:
        try:
            topo_order(content)
        except ValueError as e:
            errs.append(_err(None, "cycle", str(e)))
    return errs


def topo_order(content):
    nodes = [n for n in (content.get("nodes") or [])
             if isinstance(n, dict) and isinstance(n.get("id"), str)]
    edges = [e for e in (content.get("edges") or [])
             if isinstance(e, dict) and isinstance(e.get("from"), str)
             and isinstance(e.get("to"), str)]
    indeg = {n["id"]: 0 for n in nodes}
    out = defaultdict(list)
    for e in edges:
        if e["from"] in indeg and e["to"] in indeg:
            out[e["from"]].append(e["to"])
            indeg[e["to"]] += 1
    q = deque([n for n, d in indeg.items() if d == 0])
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if len(order) != len(nodes):
        raise ValueError("DAG 存在环")
    return order


def upstream_nodes(content, node_id):
    edges = content.get("edges") or []
    seen, stack = set(), [node_id]
    while stack:
        cur = stack.pop()
        for e in edges:
            if isinstance(e, dict) and e.get("to") == cur \
                    and e.get("from") not in seen:
                seen.add(e["from"])
                stack.append(e["from"])
    return seen
