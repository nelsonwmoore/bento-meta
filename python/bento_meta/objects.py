import re
import sys
sys.path.append('..')
from bento_meta.entity import Entity


from pdb import set_trace
# tags attr?

class Node(Entity):
  attspec = {"handle":"simple","model":"simple",
             "category":"simple","concept":"object",
             "props":"collection"}
  mapspec_ = {"label":"node",
              "key":"handle",
             "property": {"handle":"handle","model":"model","category":"category"},
             "relationship": {
               "concept": { "rel" : ":has_concept>",
                            "end_cls" : "Concept" },
               "props": { "rel" : ":has_property>",
                          "end_cls" : "Property" }
               }}

  def __init__(self, init=None):
    super().__init__(init=init)
    
class Property(Entity):
  attspec = {"handle":"simple","model":"simple",
             "value_domain":"simple","units":"simple",
             "pattern":"simple","is_required":"simple",
             "concept":"object","value_set":"object"}
  mapspec_ = {"label":"property",
              "key":"handle",
              "property": {"handle":"handle","model":"model",
                           "value_domain":"value_domain",
                           "pattern":"pattern",
                           "units":"units",
                           "is_required":"is_required"},
              "relationship": {
                "concept": { "rel" : ":has_concept>",
                             "end_cls" : "Concept" },
                "value_set": { "rel" : ":has_value_set>",
                               "end_cls" : "ValueSet" }
              }}
  def __init__(self, init=None):
    super().__init__(init=init)
  
  @property
  def terms(self):
    if self.value_set:
      return self.value_set.terms
    else:
      return None
  @property
  def values(self):
    if self.value_set:
      return [self.terms[x].value for x in self.terms]
    
class Edge(Entity):
  attspec = {"handle":"simple","model":"simple",
             "multiplicity":"simple","is_required":"simple",
             "src":"object","dst":"object",
             "concept":"object",
             "props":"collection"}
  mapspec_ = {"label":"relationship",
              "key":"handle",
              "property": {"handle":"handle","model":"model",
                           "multiplicity":"multiplicity",
                           "is_required":"is_required"},
              "relationship": {
                "src": { "rel" : ":has_src>",
                         "end_cls" : "Node" },
                "dst": { "rel" : ":has_dst>",
                         "end_cls" : "Node" },
                "concept": { "rel" : ":has_concept>",
                             "end_cls" : "Concept" },
                "props": { "rel" : ":has_property>",
                           "end_cls" : "Property" }
              }}

  def __init__(self, init=None):
    super().__init__(init=init)
  @property
  def triplet(self):
    if (self.handle and self.src and self.dst):
      return (self.handle, self.src.handle, self.dst.handle)

class Term(Entity):
  attspec={"value":"simple", "origin_id":"simple",
           "origin_definition":"simple",
           "concept":"object", "origin":"object"}
  mapspec_ = {"label":"term",
              "key":"value",
              "property": {"value":"value",
                           "origin_id":"origin_id",
                           "origin_definition":"origin_definition"},
              "relationship": {
                "concept": { "rel" : ":has_concept>",
                             "end_cls" : "Concept" },
                "origin": { "rel" : ":has_origin>",
                            "end_cls" : "Origin" }
              }}
  def __init__(self, init=None):
    super().__init__(init=init)

# for ValueSet - updating terms prop should dirty the connected Property
# (from Bento::Meta), signal need to refresh. Engineer so this happens
# here (__setattr__ override), not in Entity
class ValueSet(Entity):
  attspec={"handle":"simple","url":"simple",
           "prop":"object", "origin":"object",
           "terms":"collection"}
  mapspec_ = {"label":"value_set",
             "property": {"handle":"handle",
                          "url":"url"},
             "relationship": {
               "prop": { "rel" : "<:has_value_set",
                            "end_cls" : "Property" },
               "terms": { "rel" : ":has_term>",
                            "end_cls" : "Term" },
               "origin": { "rel" : ":has_origin>",
                          "end_cls" : "Origin" }
               }}
  def __init__(self, init=None):
    super().__init__(init=init)

class Concept(Entity):
  attspec={"terms":"collection"}
  mapspec_={"label":"concept",
            "relationship": {
              "terms" : { "rel":"<:represents",
                         "end_cls":"Term" }
            }}
  def __init__(self, init=None):
    super().__init__(init=init)

class Origin(Entity):
  attspec={"url":"simple", "is_external":"simple"}
  mapspec_={"label":"origin",
            "key":"name",
            "property": {
              "name":"name",
              "url":"url",
              "is_external":"is_external"
            }}
  def __init__(self, init=None):
    super().__init__(init=init)

class Tag(Entity):
  attspec={"value":"simple"}
  mapspec_={"label":"tag",
            "key":"value",
            "property": { "value":"value" }}
  def __init__(self,init=None):
    super().__init__(init=init)    
  
