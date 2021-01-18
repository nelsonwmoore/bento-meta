import re
import sys
import os
import io
import fastavro
sys.path.extend(['.','..'])
import pytest
from pdb import set_trace
import pkg_resources as pkgr

#from bento_meta.entity import ArgError
from bento_meta.model import Model
from bento_meta.objects import Node, Property, Edge, Term, ValueSet, Concept, Origin
from bento_meta.pfb.pfb import PFB, dataNode
from bento_meta.mdf import MDF

@pytest.fixture
def sample_model(pytestconfig):
    import os.path
    sampdir = os.path.join(pytestconfig.rootdir,"tests","samples")
    return MDF(os.path.join(sampdir,"ctdc_model_file.yaml"),
                os.path.join(sampdir,"ctdc_model_properties_file.yaml"),
                handle = "CTDC").model
@pytest.fixture
def sample_data():
    nodes = { "assignment_report": dataNode({"labels":["assignment_report"],
                        "id":"n101",
                        "assignment_report_id":"AR-001",
                        "assignment_outcome":"OFF_TRIAL",
                        "analysis_id":"ANAL-001"}),
              "arm": dataNode({"labels":["arm"],
                        "id":"n102",
                        "arm_id": "Z1A",
                        "arm_drug": "blarfinib",
                        "arm_target": "BLRF-1"}),
              "clinical_trial": dataNode({"labels":["clinical_trial"],
                        "id":"n103",
                        "clinical_trial_long_name":"BLRF-1 Long Acting Remission Forschung",
                        "clinical_trial_short_name":"BLARF",
                        "clinical_trial_type":"fictional",
                        "principal_investigators":"Arf,B.L.",
                        "lead_organization":"Blarfzentrum"})}
    links = [ ("n101", "of_arm", "n102"),
                   ("n102", "of_trial", "n103")]
    id_names = { "n101":"assignment_report",
                 "n102":"arm",
                 "n103":"clinical_trial" }
    
    return (nodes, links, id_names)
    
def test_pkg_resource():
    assert pkgr.resource_exists("bento_meta.pfb","avsc")
    assert pkgr.resource_isdir("bento_meta.pfb","avsc")
    pwd = os.path.abspath(os.curdir)
    os.chdir(pkgr.resource_filename("bento_meta.pfb","avsc"))
    assert os.path.exists("pfb.Entity.avsc")
    assert os.path.exists("pfb.Link.avsc")
    assert os.path.exists("pfb.Metadata.avsc")
    assert os.path.exists("pfb.Node.avsc")
    assert os.path.exists("pfb.Property.avsc")
    assert os.path.exists("pfb.Relation.avsc")
    assert fastavro.schema.load_schema("pfb.Metadata.avsc")
    os.chdir(pwd)
    
def test_packaged_schema_available():
    '''PFB is available (package resource works)'''
    assert PFB().construct_pfb_schema()

  # arm:
  #   Props:
  #     - show_node
  #     - arm_id
  #     - arm_target
  #     - arm_drug
  #     - pubmed_id
  # one reln -
  # of_trial:
  #   Mul: many_to_one
  #   Ends:
  #     - Src: arm
  #       Dst: clinical_trial
  #   Props: null
    
def test_node_to_pfb_meta(sample_model):
    pfb = PFB(sample_model)
    pfb.node_to_pfb_meta(sample_model.nodes["arm"])
    assert pfb.meta["arm"]
    meta = pfb.meta["arm"]
    assert meta["name"] == "arm"
    assert set(meta) == {'name','ontology_reference','values','properties','links'}
    assert set([ x["name"] for x in meta["properties"]]) == {'show_node','arm_id','arm_target','arm_drug','pubmed_id'}
    assert len(meta['links']) == 1
    assert meta['links'][0] == { "name":"of_trial", "dst":"clinical_trial", "multiplicity":"MANY_TO_ONE" }
    pass

def test_value_domain_to_avro_type(sample_model):
    pfb = PFB(sample_model)
    props = sample_model.nodes['metastatic_site'].props
    # map boolean to boolean
    assert pfb.value_domain_to_avro_type(props['show_node']) == 'boolean'
    vs_name = pfb.value_domain_to_avro_type(props['metastatic_site_name'])
    assert re.match('^vs.*',vs_name)
    assert pfb.enums[vs_name]
    assert len( pfb.enums[vs_name]["symbols"] ) == 22
    assert pfb.value_domain_to_avro_type(props['met_site_id']) == 'string'
    # check a regex type
    # check a number_with_units type
    # check a numeric type
    pass

def test_node_to_avro_schema(sample_model):
    pfb = PFB(sample_model)
    pfb.node_to_avro_schema(sample_model.nodes['metastatic_site'])
    assert pfb.avsc['metastatic_site']
    enum_name = next(iter(pfb.enums))
    assert pfb.avsc['metastatic_site'] == {
        "type": "record",
        "name": "metastatic_site",
        "fields": [
            {
                "default":None,
                "name":"show_node",
                "type":["null","boolean"]
            },
            {
                "default":None,
                "name":"met_site_id",
                "type":["null","string"]
            },
            {    
                "default":None,
                "name":"metastatic_site_name",
                "type":["null",enum_name]
            }
            ]
        }
    pass


def test_pfb_metadata_entity_for_nodes(sample_model):
    pfb = PFB(sample_model)
    hndls = [ "gene_fusion_variant","variant_report","sequencing_assay" ]
    meta = pfb.pfb_metadata_entity_for_nodes([sample_model.nodes[n] for n in hndls])
    assert meta["name"] == "Metadata"
    assert type(meta["misc"]).__name__ == "dict"
    assert len(meta["nodes"]) == 3
    pass

def test_pfb_schema_for_nodes(sample_model):
    pfb = PFB(sample_model)
    hndls = ["arm","clinical_trial","assignment_report"]
    sc = pfb.pfb_schema_for_nodes( [sample_model.nodes[n] for n in hndls] )
    assert sc
    enumsc = [ "pfb.{}".format(n) for n in pfb.enums ]
    expsc = [ "pfb.Entity", "pfb.Metadata", "pfb.Node", "pfb.Link",
              "pfb.Property", "pfb.Relation" ]
    expsc.extend(enumsc)
    # all component schemas present
    assert set([x["name"] for x in sc]) == set(expsc)
    ent ,= [x for x in sc if x["name"] =="pfb.Entity"]
    obj ,= [x for x in ent["fields"] if x["name"] == "object"]
    assert type(obj['type']) == list
    # all custom schemas present
    assert set( [x["name"] for x in obj["type"] if type(x) == dict] ) == {
        "pfb.clinical_trial", "pfb.arm", "pfb.assignment_report" }
    custom = [ x for x in obj["type"] if type(x) == dict ]
    arm ,= [x for x in custom if x["name"] == "pfb.arm"]
    arm_id_vs ,= [ x["type"] for x in arm["fields"] if x["name"] == "arm_id" ]
    # arm_id value set enum is present
    assert ent["__named_schemas"][arm_id_vs[1]]
    assert ent["__named_schemas"][arm_id_vs[1]]["type"] == "enum"
    assert set(ent["__named_schemas"][arm_id_vs[1]]["symbols"]) > {
        "Q","Z1A","G","C2","S1"}

def test_dataNode():
    dn = dataNode({"id":1,"cat":"meow"})
    assert dn
    assert dn.id == 1
    assert dn.cat == "meow"
    dn.cat = "woof"
    assert dn.cat == "woof"
    dn = dataNode({"dog":"cheep","bird":"oink"})
    assert dn.id == None
    with pytest.raises(KeyError):
        dn.thing
    assert set( [getattr(dn,i) for i in dn] ) == {"cheep","oink"}
    assert set( [getattr(dn,i) for i in dn] ) == {"cheep","oink"}
    assert set( [dn[i] for i in dn] ) == {"cheep","oink"}
        
def test_pfb_entity_for_data_nodes(sample_model, sample_data):
    # (:assignment_report)-[:of_arm]->(:arm)-[:of_trial]->(:clinical_trial)
    pfb = PFB(sample_model)
    nodes, links, id_nodes = sample_data
    data = pfb.pfb_entity_for_data_nodes(nodes.values(), id_nodes, links)
    assert data
    datad = {}
    for datum in data:
        datad[datum['name']] = datum
        assert set(datum) == {"id","name", "relations", "object"}
    
    ar = datad['pfb.assignment_report']
    assert ar
    assert ar["relations"][0] == { "dst_name":"arm", "dst_id":"n102" }
    assert ar["object"][1]["assignment_outcome"] == "OFF_TRIAL"

def test_data_validation(sample_model,sample_data):
    pfb = PFB(sample_model)
    bento_nodes={}
    nodes, links, ids = sample_data
    for node in nodes.values():
        for lbl in node.labels:
            found=None
            if (lbl in pfb.model.nodes) and (lbl not in bento_nodes):
                bento_nodes[lbl] = pfb.model.nodes[lbl]
                found=1
                break
            if not found:
                raise RuntimeError("node {} with labels {} not found in model".format(node.id,node.labels))
    pfb.pfb_metadata_entity_for_nodes(bento_nodes.values())
    pfb.pfb_schema_for_nodes(bento_nodes.values())
    pfb.pfb_entity_for_data_nodes(nodes.values(), ids, links)
    assert fastavro.validation.validate_many( pfb.data, pfb.schema )
    assert fastavro.validation.validate( { "id":"0","name":"metadata",
                                           "object":pfb.meta},
                                         pfb.schema)
    # break validation in an enumerated property
    pfb.data[1]["object"][1]["arm_id"] = "ZZYXX";
    with pytest.raises(Exception, match="arm_id is <ZZYXX>.*expected"):
        fastavro.validation.validate( pfb.data[1],pfb.schema)
    

def test_write_data(sample_model):
    pfb = PFB(sample_model)
    nodes = [ dataNode({"labels":["assignment_report"],
                        "id":"n101",
                        "assignment_report_id":"AR-001",
                        "assignment_outcome":"OFF_TRIAL",
                        "analysis_id":"ANAL-001"}),
              dataNode({"labels":["arm"],
                        "id":"n102",
                        "arm_id": "Z1A",
                        "arm_drug": "blarfinib",
                        "arm_target": "BLRF-1"}),
              dataNode({"labels":["clinical_trial"],
                        "id":"n103",
                        "clinical_trial_long_name":"BLRF-1 Long Acting Remission Forschung",
                        "clinical_trial_short_name":"BLARF",
                        "clinical_trial_type":"fictional",
                        "principal_investigators":"Arf,B.L.",
                        "lead_organization":"Blarfzentrum"})]
    links = [ ("n101", "of_arm", "n102"),
                   ("n102", "of_trial", "n103")]
    b = io.BytesIO(b"")
    pfb.write_data(b,nodes,links)
    msg = b.getvalue()
    assert len(msg)

