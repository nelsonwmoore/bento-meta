import sys
import re
import pytest
from pdb import set_trace
sys.path.insert(0, '.')
sys.path.insert(0, '..')
from bento_meta.util.cypher import (
    N, N0, R, R0, P, T, G,
    Clause, Match, Where, Return, Statement,
    Func, count, exists, group, And, Or, Not,
    _pattern, _as, _condition, _return,
    _plain, _anon, _var
)


def test_entities():
    # nodes
    assert isinstance(N0(), N)
    assert not N0().label
    assert not N0().props
    assert not N0().As
    assert not N0().var

    n = N()
    assert n.var
    assert re.match("^n[0-9]+$", n.var)
    m = N(label="thing")
    assert m.label == "thing"
    assert n.var != m.var

    assert n.pattern() == "({})".format(n.var)
    assert m.pattern() == "({}:thing)".format(m.var)
    assert _pattern(m) == "({}:thing)".format(m.var)
    assert not n.condition()
    assert not m.condition()
    assert not _condition(n)
    assert n.Return() == n.var
    assert m.Return() == m.var
    assert _return(m) == m.var

    assert _return(_as(m, "eddie")) == "{} as eddie".format(m.var)
    
    x = N(label="thing", As="dude")
    assert x.label == "thing" and x.As == "dude"
    assert x.Return() == "{} as dude".format(x.var)
    
    # relationships
    assert isinstance(R0(), R)
    assert not R0().Type
    assert not R0().props
    assert not R0().var
    
    r = R(Type="has_a")
    assert re.match("^r[0-9]+$", r.var)
    s = R(Type="is_a")
    assert r.var != s.var
    assert r.pattern() == "-[{}:has_a]-".format(r.var)
    assert _pattern(r) == "-[{}:has_a]-".format(r.var)
    assert not r.condition()
    assert not _condition(r)
    assert r.Return() == "{}".format(r.var)
    assert _return(r) == "{}".format(r.var)
    
    # props
    p = P(handle="height")
    assert p.handle == "height"
    q = P(handle="weight", value=12)
    assert type(q.value) == int
    assert q.value == 12
    l = P(handle="color", value="blue")
    assert type(l.value) == str
    assert l.value == "blue"
    t = P(handle="spin", value="$parm")

    assert not p.condition()
    assert not q.condition()

    w = N(label="item", props=q)
    assert q.condition() == "{}.weight = 12".format(w.var)
    assert _condition(q) == "{}.weight = 12".format(w.var)
    x = N(label="item", props=l)
    assert _condition(l) == "{}.color = 'blue'".format(x.var)
    y = N(label="item", props=t)
    assert _condition(t) == "{}.spin = $parm".format(y.var)

    z = y.relate_to(r, x)
    assert isinstance(z, T)
    assert z.pattern() == (
        "({}:item {{spin:$parm}})-[{}:has_a]->({}:item "
        "{{color:'blue'}})"
        ).format(y.var, r.var, x.var)
    assert z.pattern() == z.condition()
    assert _pattern(z) == _condition(z)

    u = s.relate(w, x)
    assert isinstance(u, T)
    assert _pattern(_plain(u)) == (
        "({}:item)-[{}:is_a]->({}:item)"
        ).format(w.var, s.var, x.var)

    u = _anon(s).relate(w, _anon(x))
    assert _pattern(_plain(u)) == (
        "({}:item)-[:is_a]->(:item)"
        ).format(w.var)

    u = R0().relate(_var(w), _var(x))
    assert _pattern(_plain(u)) == (
        "({})-->({})"
        ).format(w.var, x.var)

    assert _pattern(R0().relate(N0(), N0())) == "()-->()"


def test_paths():
    # happy paths:
    # G(N, R, N), G(T, T), G(N, R, T), G(T, R, N)
    # G(N, R, P), G(G, R, N)
    # G(N, R, N, R, N, R, N), G(T, G), G(G, T)
    # G(G, G)
    # G(G, R, N, R, T) ...
    # unhappy paths: with pytest.raises(Exception)
    # G(N), G(R), G(N, R), G(R, N), G(N, N)
    # G(N, T), G(R, T), G(N, G), G(R, G)
    # G(N, R, N, R, N, R)
    nodes = [N(label="case"), N(label="sample"), N(label="aliquot"),
             N(label="file")]
    edges = [R(Type="of_case"), R(Type="of_sample"), R(Type="of_aliquot")]

    t1 = edges[0].relate(nodes[1], nodes[0])
    t2 = edges[1].relate(nodes[2], nodes[1])
    t3 = edges[2].relate(nodes[3], nodes[2])

    pth0 = G(nodes[0], edges[0], nodes[1])  # G(N, R, N)
    pth1 = G(t1)  # G(T)
    pth2 = G(t1, t2)  # G(T, T)
    pth3 = G(t2)
    pth4 = G(pth1, pth3)  # G(G, G)
    pth5 = G(pth4, edges[2], nodes[3])  # G(G, R, N)
    pth6 = G(t2, edges[2], nodes[3])  # G(T, R, N)
    pth7 = G(nodes[0], edges[0], t2)  # G(N, R, T)
    pth8 = G(pth1, edges[1], nodes[2], edges[2], t3)
    
    with pytest.raises(RuntimeError, match="do not define a complete Path"):
        G(nodes[0])  # G(N)
    with pytest.raises(RuntimeError, match="is not valid at arg position 1"):
        G(edges[0])  # G(R)
    with pytest.raises(RuntimeError, match="do not define a complete Path"):
        G(nodes[0], edges[0])  # G(N, R)
    with pytest.raises(RuntimeError, match="is not valid at arg position 2"):
        G(nodes[0], nodes[1])  # G(N, N)
    with pytest.raises(RuntimeError, match="is not valid at arg position 2"):
        G(nodes[0], t1)  # G(N, T)
    with pytest.raises(RuntimeError, match="is not valid at arg position 1"):
        G(edges[1], t1)  # G(R, T)
    with pytest.raises(RuntimeError, match="do not define a complete Path"):
        G(nodes[0], edges[0], nodes[1], nodes[2], edges[1])  # G(N, R, N, N, R)

    # two overlapping triples work: call it a feature
    G(nodes[1], edges[0], nodes[0], nodes[2], edges[1], nodes[1])
    # equivalent
    G(nodes[2], edges[1], nodes[1], edges[0], nodes[0])

    with pytest.raises(RuntimeError, match="do not overlap"):
        G(t1, t3)
    # same semantics as G(t1, t2), but not the same objects:
    with pytest.raises(RuntimeError, match="do not overlap"):
        G(t1, R(Type=edges[1].Type).relate(N(label=nodes[2].label),
                                           N(label=nodes[1].label)))

def test_clauses():

    n = N(label="node", props={"model": "ICDC", "handle": "diagnosis"})
    m = N(label="property", props={"handle": "disease_type"})
    t = _anon(R(Type="has_property")).relate(n, m)

    c = count(n)
    assert isinstance(c, count)
    assert isinstance(c, Func)
    assert str(c) == "count({})".format(n.var)
    assert str(count("this")) == "count(this)"
    x = exists(m.props['handle'])
    assert isinstance(x, exists)
    assert isinstance(x, Func)
    assert str(x) == "exists({}.handle)".format(m.var)
    assert str(exists("this.that")) == "exists(this.that)"

    match = Match(t)
    assert isinstance(match, Match)
    assert isinstance(match, Clause)
    assert str(match) == (
        "MATCH ({}:node {{model:'ICDC',handle:'diagnosis'}})"
        "-[:has_property]->({}:property {{handle:'disease_type'}})"
        ).format(n.var, m.var)

    where = Where(*t.nodes())
    assert isinstance(where, Where)
    assert isinstance(where, Clause)
    assert str(where) == (
        "WHERE {n}.model = 'ICDC' AND {n}.handle = 'diagnosis' "
        "AND {m}.handle = 'disease_type'"
        ).format(n=n.var, m=m.var)

    ret = Return(t)
    assert isinstance(ret, Return)
    assert isinstance(ret, Clause)
    assert str(ret) == (
        "RETURN {n}, {m}"
        ).format(n=n.var, m=m.var)


def test_statments():
    n = N(label="node", props={"model": "ICDC", "handle": "diagnosis"})
    m = N(label="property", props={"handle": "disease_type"})
    t = _anon(R(Type="has_property")).relate(n, m)
    p = P(handle='boog')
    p.entity = n

    assert str(
        Statement(
            Match(_var(_plain(t))),
            Where(exists(m.props['handle']), n),
            Return(count(n))
            )
        ) == (
            "MATCH ({n})-[:has_property]->({m}) "
            "WHERE exists({m}.handle) AND {n}.model = 'ICDC' AND "
            "{n}.handle = 'diagnosis' "
            "RETURN count({n})"
            ).format(n=n.var, m=m.var)

    assert str(
        Statement(
            Match(_var(_plain(t))),
            Where(group(And(exists(m.props['handle']), n.props['model'])),
                  Not(n.props['handle'])),
            Return(p),
            'LIMIT 10'
            )
        ) == (
            "MATCH ({n})-[:has_property]->({m}) "
            "WHERE (exists({m}.handle) AND {n}.model = 'ICDC') AND NOT "
            "{n}.handle = 'diagnosis' "
            "RETURN {n}.boog LIMIT 10"
            ).format(n=n.var, m=m.var)
