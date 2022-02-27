"""
mdb.loaders: load models into an MDB instance consistently
"""
from bento_meta.mdf import MDF
from bento_meta.mdb import WriteableMDB
from bento_meta.util.cypher.entities import (
    N, R, P, T, G, _var,
    )
from bento_meta.util.cypher.clauses import (
    Match, Create, Merge, Set, OnMatchSet, OnCreateSet,
    Statement,
    )

def load_mdf(mdf, mdb, _commit=None):
    """Load an MDF object into an MDB instance"""
    load_model(mdf.model, mdb, _commit)

def load_model(model, mdb, _commit=None):
    """Load a model object into an MDB instance."""
    if not isinstance(mdb, WriteableMDB):
        raise RuntimeError("mdb object must be a WriteableMDB")
    cStatements = []
    cNodes = {}
    for nd in model.nodes:
        node = model.nodes[nd]
        cNode = _cEntity(node, model, _commit)
        cStatements.append(
            Statement(
                Create(cNode)
                )
            )
        cNodes[node.handle] = cNode
        cProps = []
        if node.tags:
            cStatements.extend(
                _tag_statements(node, cNode, _commit)
                )
        if node.props:
            cStatements.extend(
                _prop_statements(node, cNode, model, _commit)
                )
    # node nodes and node-property nodes now exist
    # nodes are linked to properties
    for rl in model.edges:
        edge = model.edges[rl]
        cEdge = _cEntity(edge, model, _commit)
        cSrc = _cEntity(edge.src, model, _commit)
        cDst = _cEntity(edge.dst, model, _commit)

        if edge.multiplicity:
            cEdge._add_props({"multiplicity": edge.multiplicity})
        if edge.is_required:
            cEdge._add_props({"is_required": edge.is_required})
        cStatements.extend([
            Statement(
                Create(cEdge)
                ),
            Statement(
                Match(cEdge, cSrc, cDst),
                Create(
                    G(R(Type="has_src").relate(_var(cEdge), _var(cSrc)),
                      R(Type="has_dst").relate(_var(cEdge), _var(cDst)))
                    )
                )])
        if edge.tags:
            cStatements.extend(
                _tag_statements(edge, cEdge, _commit)
                )
        if edge.props:
            cStatements.extend(
                _prop_statements(edge, cEdge, model, _commit)
                )
    # edge node and edge-property nodes now exist

    return True


def _cEntity(ent, model, _commit):
    label = type(ent).__name__.lower()
    if label == 'edge':
        label = 'relationship'
    cEnt = N(label=label,
             props={"handle": ent.handle,
                    "model": model.handle})
    if _commit:
        cEnt._add_props({"_commit": _commit})
    if ent.nanoid:
        cEnt._add_props({"nanoid": ent.nanoid})
    if ent.desc:
        cEnt._add_props({"desc": ent.desc})
    return ent
         
def _tag_statements(ent, cEnt, _commit):
    stmts = []
    cTags = []
    if ent.tags:
        for t in ent.tags.values():
            cTag = N(label="tag",
                     props={"key": t.key,
                            "value": t.value})
            if _commit:
                cTag._add_props({"_commit": _commit})
            if t.nanoid:
                cTag._add_props({"nanoid": t.nanoid})
            if t.desc:
                cTag._add_props({"desc": t.desc})
            cTags.append(cTag)
    for ct in cTags:
        stmts.append(
            Statement(
                Match(cEnt),
                Create(R(Type="has_tag").relate(_var(cEnt), ct))
                )
            )
    return stmts

def _prop_statements(ent, cEnt, model, _commit):
    stmts = []
    for p in ent.props.values():
        cProp = _cEntity(p, model, _commit)
        cProp._add_props({"value_domain": p.value_domain})
        stmts.extend([
            Statement(
                Create(cProp)
                ),
                Statement(
                    Match(cEnt, cProp),
                    Create(R(Type="has_property").relate(
                        _var(cEnt), _var(cProp)))
                    )
            ])
        if p.tags:
            stmts.extend(
                _tag_statements(p, cProp, _commit)
                )
    return stmts
