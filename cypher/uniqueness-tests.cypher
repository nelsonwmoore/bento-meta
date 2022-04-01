match (n:node) with [n.model, n.handle] as l with l, count(l) as ct return ct, count(ct);
match (n)-[:has_property]->(p:property) with [p.model, n.handle, p.handle] as l with l, count(l) as ct return ct, count(ct);
match (s:node)<-[:has_src]-(r:relationship)-[:has_dst]->(d:node) with [r.model, r.handle, s.handle, d.handle] as l with l, count(l) as ct return ct, count(ct);
match (n)-->(p:property {value_domain:"value_set"})-->(v:value_set) with [n.handle, p.handle, v.handle] as l with l, count(l) as ct return ct, count(ct);
match (t:term)  with [t.value, t.origin_name, t.origin_id, t.origin_version] as l with l, count(l) as ct return ct, count(ct);
