import re
import sys
sys.path.extend(['.','..'])
import pytest
from pdb import set_trace
from bento_meta.mdf import MDF
from bento_meta.entity import ArgError
from bento_meta.model import Model
from bento_meta.objects import Node, Property, Edge, Term, ValueSet, Concept, Origin

def test_class():
  m = MDF(handle='test')
  assert isinstance(m,MDF)
  with pytest.raises(ArgError,match="arg handle= must"):
    MDF()

def test_load_yaml():
  m = MDF(handle='test')
  m.files = ['tests/samples/ctdc_model_file.yaml', 'tests/samples/ctdc_model_properties_file.yaml']
  m.load_yaml()

def test_create_model():
  m = MDF(handle='test')
  m.files = ['tests/samples/ctdc_model_file.yaml', 'tests/samples/ctdc_model_properties_file.yaml']
  m.load_yaml()
  m.create_model()

def test_created_model():
  m = MDF('tests/samples/test-model.yml',handle='test')
  assert isinstance(m.model,Model)
  assert set([x.handle for x in m.model.nodes.values()]) == {'case','sample','file','diagnosis'}
  assert set([x.triplet for x in m.model.edges.values()])== {
    ('of_case','sample','case'),('of_case','diagnosis','case'),
    ('of_sample','file','sample'),('derived_from','file','file'),
    ('derived_from','sample','sample') }
  assert set([x.handle for x in m.model.props.values()]) == {
    'case_id','patient_id','sample_type','amount','md5sum','file_name',
    'file_size', 'disease','days_to_sample','workflow_id','id'}
  file_ = m.model.nodes['file']
  assert file_
  assert file_['props']
  assert set([x.handle for x in file_.props.values()])=={
    'md5sum','file_name','file_size'}
  assert m.model.nodes['file'].props['md5sum'].value_domain == 'regexp'
  assert m.model.nodes['file'].props['md5sum'].pattern
  amount = m.model.props[('sample','amount')]
  assert amount
  assert amount.value_domain == 'number'
  assert amount.units == 'mg'
  file_size = m.model.props[('file','file_size')]
  assert file_size
  assert file_size.units == 'Gb;Mb'
  derived_from = m.model.edges[('derived_from','sample','sample')]
  assert derived_from
  assert len(derived_from.props.keys()) == 1
  assert next(iter(derived_from.props.values())).handle == 'id'
  
  
