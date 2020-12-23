import re
import sys
import os
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
                "default":"null",
                "name":"show_node",
                "type":"boolean"
            },
            {
                "default":"null",
                "name":"met_site_id",
                "type":"string"
            },
            {    
                "default":"null",
                "name":"metastatic_site_name",
                "type":enum_name
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
    # all component schemas present
    assert set([x["name"] for x in sc]) == {
        "pfb.Entity", "pfb.Metadata", "pfb.Node", "pfb.Link", "pfb.Property",
        "pfb.Relation" }
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
    assert ent["__named_schemas"][arm_id_vs]
    assert ent["__named_schemas"][arm_id_vs]["type"] == "enum"
    assert set(ent["__named_schemas"][arm_id_vs]["symbols"]) > {
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
        
def test_pfb_entity_for_data_nodes(sample_model):
    # (:assignment_report)-[:of_arm]->(:arm)-[:of_trial]->(:clinical_trial)
    pfb = PFB(sample_model)
    nodes = [ dataNode({"labels":["assignment_report"],
                        "id":101,
                        "assignment_report_id":"AR-001",
                        "assignment_outcome":"OFF_TRIAL",
                        "analysis_id":"ANAL-001"}),
              dataNode({"labels":["arm"],
                        "id":102,
                        "arm_id": "Z1A",
                        "arm_drug": "blarfinib",
                        "arm_target": "BLRF-1"}),
              dataNode({"labels":["clinical_trial"],
                        "id":103,
                        "clinical_trial_long_name":"BLRF-1 Long Acting Remission Forschung",
                        "clinical_trial_short_name":"BLARF",
                        "clinical_trial_type":"fictional",
                        "principal_investigators":"Arf,B.L.",
                        "lead_organization":"Blarfzentrum"})]
    node_names = { 101:"assignment_report",
                   102:"arm",
                   103:"clinical_trial" }
    data_links = [ (101, "of_arm", 102),
                   (102, "of_trial", 103)]
    data = pfb.pfb_entity_for_data_nodes(nodes, node_names, data_links)
    assert data
    for datum in data:
        assert set(datum) == {"id","name", "relations", "object"}
    
    ar ,= [x for x in data if x["name"] == "assignment_report"]
    assert ar
    assert ar["relations"][0] == { "dst_name":"arm", "dst_id":102 }
    assert ar["object"]["assignment_outcome"] == "OFF_TRIAL"
    
