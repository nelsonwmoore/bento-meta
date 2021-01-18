# don't forget to
#  python setup.py develop
# to get access to avsc/ via pkg_resources
import pkg_resources as pkgr
from fastavro.schema import load_schema
from fastavro.write import writer
from fastavro.read import reader
from fastavro.validation import validate_many
from warnings import warn
import json
import tempfile
import os

from bento_meta.entity import ArgError

from pdb import set_trace
    
class PFB(object):
    """PFB serialization facilities for Bento data

Blah blah blah
"""
    schema = {}
    enums = {}
    avsc = {}
    meta = {}
    data = []
    payload = []
    
    def __init__(self, model=None):
        """Object to contain customized PFB schema and provide read/write facilities
"""
        self.model = model
        self.schema = None
        self.enums = {}
        self.avsc = {}
        self.meta = {}
        self.data = []
        self.payload = []
        pass

    def construct_pfb_schema(self, avro_nodes=[]):
        """Create a PFB Entity schema, including a list of Avro nodes (data node schemas) derived from the model.
:param list avro_nodes: List of plain Avro data node schemas
"""
        curdir = os.getcwd()
        os.chdir( pkgr.resource_filename("bento_meta.pfb","avsc") )
        schema = None
        enums = {}

        # write the enum schemas to files for recursive loading by load_schema
        for k in self.enums:
            with open("pfb.{}.avsc".format(k),"w") as ef:
                json.dump(self.enums[k],ef)
            
        with open("pfb.Entity.avsc","r") as Entity:
            # load Entity schema as simple json
            schema_json = json.load( Entity )
            # find the "object" hash 
            [object] = [ x for x in schema_json["fields"] if x["name"] == "object" ]
            # add the custom schemas (as names) to the object.type array
            object["type"].extend(avro_nodes)
            # dump json to a tempfile to take advantage of fastavro avsc 
            # name resolution in fastavro.schema.load_schema()
            with tempfile.NamedTemporaryFile(mode='w+',dir='.', delete=True) as tf:
                json.dump(schema_json,tf)
                tf.seek(0)
                # load the customized schema
                schema = load_schema(tf.name)
            pass

        # done with enum schema files
        for k in self.enums:
            os.remove("pfb.{}.avsc".format(k))
            
        os.chdir(curdir)
        self.schema = schema
        return self.schema

    def node_to_pfb_meta(self,node):
        """Rewrite a bento_meta Node object as a PFB Metadata component.
Store the metadata component in the PFB object attribute PFB.meta, and return it.
"""
        if node.handle in self.meta:
            return self.meta[node.handle];
        meta = { "name":node.handle }
        # if node has an associated term from NCIT
        concept_code = None
        if node.concept:
            for t in node.concept.terms.values():
                if t.origin.name == "NCIT":
                    if t.origin_id:
                        concept_code = t.origin_id
                        break
        if concept_code:
            meta["ontology_reference"] = "NCIT"
            meta["values"] = { "concept_code": concept_code }
        else:
            meta["ontology_reference"] = ""
            meta["values"] = {}

        # properties
        props = []
        for p in node.props.values():
            e = { "name":p.handle }
            concept_code = None
            if p.concept:
                for t in p.concept.terms.values():
                    if t.origin.name == "NCIT":
                        if t.origin_id:
                            concept_code = t.origin_id
                            break
            if concept_code:
                e["ontology_reference"] = "NCIT"
                e["values"] = { "concept_code": concept_code }
            else:
                e["ontology_reference"] = ""
                e["values"] = {}
            props.append(e)
        meta["properties"] = props

        # links
        links = []
        for l in self.model.edges_by_src(node):
            links.append({
                "name": l.handle,
                "dst": l.dst.handle,
                "multiplicity": l.multiplicity.upper()
                })
        meta["links"] = links
        self.meta[node.handle] = meta
        return meta
    
    def node_to_avro_schema(self,node):
        """Rewrite a bento_meta Node object as a plain Avro data node schema
Store Avro schema in PFB object attribute PFB.avsc and return it.
"""
        if node.handle in self.avsc:
            return self.avsc[node.handle]
        avs = { "type":"record", "name":node.handle}
        avs["fields"] = []
        # simple attributes -> PFB fields
        
        for p in node.props.values():
            fld_avs = {
                "name":p.handle,
                "type": self.value_domain_to_avro_type( p )
                }
            if not p.is_required:
                fld_avs["type"] = ["null", fld_avs["type"]]
                fld_avs["default"] = None
            avs["fields"].append(fld_avs)
        self.avsc[node.handle] = avs
        return avs

    def value_domain_to_avro_type(self,prop):
        """Convert a property's bento-mdf value domain to an Avro type
:param Property prop: the `Property` node

Note: For value set (enum) value domains, this method creates an Avro enum type
and places it in the self.enums dict, and returns the type name "vs_<prop.handle>"
as the Avro type.
"""
        btype = prop.value_domain
        atype = None
        if not btype:
            atype = "null"
        if btype in ["string", "boolean"]:  # direct map
            atype = btype
        if btype in ["TBD", "url", "datetime"]:
            # reduced constraint (needs attn)
            atype = "string"
        if btype in ['number', 'integer']:  # numeric data
            atype = 'int' if type == "integer" else "double"
        if type(btype) is dict:  # number_with_units, or regex pattern constraint
            if "pattern" in btype:
                atype = {
                    "type":"record",
                    "namespace":"pfb",
                    "name":"string_for_"+prop.handle,
                    "fields": [
                        {"name":"value", "type":"string"},
                        {"name":"pattern", "type":"string",
                         "default":type["pattern"] }
                    ]}
            elif "units" in btype:
                value_type = 'int' if btype == "integer" else "double"    
                en = { "name":prop.handle+"_units","type":"enum","symbols":[] }
                for u in prop.units.split(';'):
                    en["symbols"].append(u)
                atype = {
                    "type":"record",
                    "namespace":"pfb",
                    "name":"number_with_units_for_"+prop.handle,
                    "fields": [
                        {"name":"value", "type":value_type},
                        {"name":"units", "type":en }
                    ]}
            else:
                raise ArgError("Value domain structure {} cannot be interpreted".format(type))
        if btype == "value_set": # create (if nec) acceptable value enum and return its name
            vs = prop.value_set
            vs_name = "vs_{}".format(vs._id)
            if vs_name not in self.enums:
                self.enums[vs_name] = {
                    "type": "enum",
                    "namespace": "pfb",
                    "name": vs_name,
                    "symbols": [t.value for t in prop.terms.values()]
                    }
            atype = vs_name
        return atype

    def pfb_metadata_entity_for_nodes(self, nodes=[]):
        for n in nodes:
            self.node_to_pfb_meta(n)
        hndls = [n.handle for n in nodes]
        self.meta =  {
            "name": "Metadata",
            "misc": {},
            "nodes": [self.meta[nm] for nm in hndls]
            }
        return self.meta
    
    def pfb_schema_for_nodes(self, nodes=[]):
        self.avsc = {}
        for n in nodes:
            self.node_to_avro_schema(n) 
        return self.construct_pfb_schema(self.avsc.values())

    def pfb_entity_for_data_nodes(self, data_nodes, node_names={},data_links=[]):
        # collect edge and destination by src - facilitate creating "relations"
        # element for each data node
        self.data=[]
        by_src = {}
        for link in data_links:
            src,edge,dst = link
            if src not in by_src:
                by_src[src] = []
            by_src[src].append( (edge, dst) )
        for node in data_nodes:
            if not type(node).__name__ in ("neo4j.Graph.Node", "dataNode"):
                raise TypeError("node must be a neo4j.Graph.Node or a dataNode")
            pfb_entity = {"id":node.id,"object":{},"relations":[]}
            if node.id in node_names:
                pfb_entity["name"] = "pfb."+node_names[node.id]
            else:
                raise RuntimeError("node with id {} does not have an associated type name".format(node.id))
            pfb_entity["object"] = (pfb_entity["name"],{})
            for p in node:
                pfb_entity["object"][1][p] = node[p]
            if node.id in by_src:
                for edge,dst in by_src[node.id]:
                    pfb_entity["relations"].append(
                        { "dst_name":node_names[dst],
                              "dst_id": dst })
            self.data.append(pfb_entity)
        return self.data

    def write_data(self, flo, data_nodes, data_links=[], validate=True, **kwargs):
        """Write a PFB message directly from a list of data nodes (not bento-meta 
nodes). Data nodes must have types that are represented in the PFB object's model.
:param filelike flo: a file-like object open for binary writing
:param list data_nodes: list of `neo4j.graph.Node` or `dataNode`
:param list data_links: list of triples in the form (<node_id>,<edge handle>, <node_id>) linking source to destination data nodes via a model edge
:param boolean validate: whether to validate the message with fastavro
:param **kwargs: remaining keyword args are passed to `fastavro.write`
"""
        # steps:
        # collect a list of bento nodes corresponding to the data nodes
        # create the pfb schema with list of bento nodes
        # include self.enums in "the right place" : think about
        # create the payload for writing:
        # - create the Metadata entity with list of bento nodes
        #   - "id" key : "metadata"
        #   - "name" key : "metadata"
        # - create the data entity for each data_node
        #   - "object" key = data_node element
        #   - "relations"  key  = data_links with data_node element as source
        #   - "id" key = must be given in the data_node element and
        #     used in data_links entries
        # write(file, self.schema, payload) 

        bento_nodes={}
        node_names={}
        for node in data_nodes:
            for lbl in node.labels:
                found=None
                if (lbl in self.model.nodes) and (lbl not in bento_nodes):
                    bento_nodes[lbl] = self.model.nodes[lbl]
                    node_names[node.id] = lbl
                    found=1
                    break
                if not found:
                    raise RuntimeError("node {} with labels {} not found in model".format(node.id,node.labels))
        self.pfb_metadata_entity_for_nodes(bento_nodes.values())
        self.pfb_schema_for_nodes(bento_nodes.values())
        self.pfb_entity_for_data_nodes(data_nodes, node_names, data_links)
        self.payload.append(
            {"id":"_metadata","name":"metadata","object":self.meta})
        self.payload.extend(self.data)
        if (validate):
            validate_many(self.payload,self.schema,raise_errors=True)
        writer(flo, self.schema, self.payload, **kwargs)
        
            
class dataNode(object):
    """Simple wrapper to provide attributes to a dict. Quacks like neo4j.Graph.Node."""
    def __init__(self,init):
        if not type(init) == dict:
            raise ArgError("Construct a dataNode with a dict")
        self.data = init
        if not self.data.get("id"):
            self.data["id"] = None
        if not self.data.get("labels"):
            self.data["labels"] = []
    def __getattribute__(self, att):
        if att == "data":
            return object.__getattribute__(self,att)
        else:
            return self.data[att]
    def __setattr__(self,att,val):
        if att == "data":
            object.__setattr__(self,att,val)
        else:
            self.data[att] = val;
    def __getitem__(self,att):
        return getattr(self,att)
    def __iter__(self):
        props = [k for k in self.data.keys() if not k in ["id","labels"]]
        return iter(props)
