import re
import sys
sys.path.extend(['.','..'])
import pytest
from pdb import set_trace

#from bento_meta.entity import ArgError
from bento_meta.model import Model
from bento_meta.objects import Node, Property, Edge, Term, ValueSet, Concept, Origin
from bento_meta.pfb.pfb import PFB

@pytest.fixture
def sample_model(pytestconfig):
    import os.path
    from bento_meta.mdf import MDF
    sampdir = os.path.join(pytestconfig.rootdir,"tests","samples")
    return MDF(os.path.join(sampdir,"ctdc_model_file.yaml"),
                os.path.join(sampdir,"ctdc_model_properties_file.yaml"),
                handle = "CTDC").model

def test_packaged_schema_available():
    '''PFB is available (package resource works)'''
    assert PFB().construct_pfb_schema().schema

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
    # map TBD type to 'string'
    assert pfb.value_domain_to_avro_type(props['show_node']) == 'string'
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


def test_pfb_metadata_entity_for_nodes():
    pass

def test_pfb_schema_for_nodes():
    pass

def test_pfb_entity_for_data_nodes():
    pass


    
