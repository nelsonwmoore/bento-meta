import re
from copy import deepcopy
from pdb import set_trace
from collections import UserDict

class ArgError(Exception):
  pass

class Entity(object):
  pvt_attr=['pvt','neoid','dirty','removed_entities','attspec',
            'mapspec','belongs']
  attspec_={"_id":"simple", "desc":"simple",
           "_next":"object", "_prev":"object",
           "_from":"simple", "_to":"simple",
           "tags":"collection"}
  attspec=attspec_
  mapspec_={
    "label":None,
    "key":"_id",
    "property": {
      "_id":"id",
      "desc":"desc",
      "_from":"_from",
      "_to":"_to"
      },
    "relationship": {
      "_next": { "rel" : ":_next>",
                 "end_cls" : set() },
      "_prev": { "rel" : ":_prev>",
                 "end_cls" : set() },
      "tags": { "rel" : ":has_tag",
                "end_cls" : {"Tag"} }
    }}
  object_map=None
  version_count=None
  versioning_on=False
  
  def __init__(self,init=None):
    if not set(type(self).attspec.values()) <= set(['simple','object','collection']):
      raise ArgError("unknown attribute type in attspec")
    # private
    self.pvt={}
    self.neoid=None
    self.dirty=1
    self.removed_entities=[]
    self.belongs = {}
    if type(self).versioning_on:
      self.mergespec()
      self._from = type(self).version_count

    # merge to universal map
    type(self).mergespec()

    if init:
      if isinstance(init,Entity):
        self.set_with_entity(init)
      elif isinstance(init, dict):
        self.set_with_dict(init)
      elif type(init).__name__ == 'Node': # neo4j.graph.Node - but don't want to import that
        self.set_with_node(init)
    for att in type(self).attspec:
      if not att in self.__dict__:
        if self.attspec[att] == 'collection':
          setattr(self,att, CollValue({},owner=self,owner_key=att))
        else:
          setattr(self,att,None)
          
  @classmethod
  def mergespec(cls):
    cls.attspec.update(Entity.attspec_)
    mo=deepcopy(Entity.mapspec_)
    cs=cls.mapspec_
    if "label" in cs:
      mo["label"] = cs["label"]
    if "key" in cs:
      mo["key"] = cs["key"]
    if "property" in cs:
      mo["property"].update(cs["property"])
    if "relationship" in cs:
      mo["relationship"].update(cs["relationship"])    
    mo["relationship"]["_next"]["end_cls"]={cls.__name__}
    mo["relationship"]["_prev"]["end_cls"]={cls.__name__}
    cls._mapspec=mo

  @classmethod
  def mapspec(cls):
    if not hasattr(cls,'_mapspec'):
      cls.mergespec()
    return cls._mapspec
  @classmethod
  def versioning(cls,on=None):
    if on==None:
      return cls.versioning_on
    cls.versioning_on=on
    return cls.versioning_on
  @classmethod
  def set_version_count(cls,ct):
    if not isinstance(ct, int) or ct < 0:
      raise ArgError("arg must be a positive integer")
    cls.version_count=ct
  @property
  def dirty(self):
    return self.pvt['dirty']
  @dirty.setter
  def dirty(self,value):
    self.pvt['dirty']=value
  @property
  def versioned(self):
    return self._from
  @property
  def removed_entities(self):
    return self.pvt['removed_entities']
  @property
  def object_map(self):
    return self.pvt['object_map']
  @property
  def belongs(self):
    return self.pvt['belongs']
  def clear_removed_entities(self):
    self.pvt['removed_entities']=[]
  def set_with_dict(self, init):
    for att in type(self).attspec:
      if att in init:
        if type(self).attspec[att] == 'collection':
          setattr(self,att,CollValue(init[att],owner=self,owner_key=att))
        else:
          setattr(self,att,init[att])
  def set_with_node(self, init):
    # this unsets any attribute that is not present in the Node's properties
    for att in [a for a in type(self).attspec if type(self).attspec[a]=='simple']:
      patt = type(self).mapspec()['property'][att]
      if patt in init:
        setattr(self,att,init[patt])
      else:
        setattr(self,att,None)
    self.neoid = init.id

  def set_with_entity(self,ent):
    if not isinstance(self, type(ent)):
      raise ArgError("class mismatch: I am a {slf}, but arg is a {ent}".format(
        slf=type(self).__name__,
        ent=type(ent).__name__))
    for k in type(self).attspec:
      atts = type(self).attspec[k]
      if k=="_next" or k=="_prev":
        break
      if atts=='simple':
        setattr(self,k,getattr(ent,k))
      elif atts=='object':
        setattr(self,k,getattr(ent,k))
      elif atts=='collection':
        setattr(self,k, CollValue(getattr(ent,k),owner=self,owner_key=k))
        pass
      else:
        raise RuntimeError("unknown attribute type '{atts}'".format(atts=atts))
    for okey in ent.belongs:
      self.belongs[okey] = ent.belongs[okey]
    self.neoid = ent.neoid
    self.dirty = 1
    return self
  
  def __getattribute__(self, name):
    if name in type(self).attspec:
      # declared attr, send to __getattr__ for magic
      return self.__getattr__(name)
    else:
     return object.__getattribute__(self,name)
    
  def __getattr__(self, name):
    if name in Entity.pvt_attr:
      return self.__dict__['pvt'][name]
    elif name in type(self).attspec:
      if not name in self.__dict__ or self.__dict__[name]==None:
        return None
      if type(self).attspec[name] == 'object':
        # magic - lazy getting
        if self.__dict__[name].dirty < 0:
          self.__dict__[name].dget()
      return self.__dict__[name]
    else:
      raise AttributeError("get: attribute '{name}' neither private nor declared for subclass {cls}".format(name=name,cls=type(self).__name__))

  def __setattr__(self, name, value):
    if name == 'pvt':
      self.__dict__['pvt'] = value
    elif name in Entity.pvt_attr:
      self.__dict__['pvt'][name]=value
    elif name in type(self).attspec:
      self._check_value(name,value)
      if name in ['_prev','_next','_from','_to']:
        self.dirty=1
        self.__dict__[name] = value
      else:
        self._set_declared_attr(name,value)
    else:
      raise AttributeError("set: attribute '{name}' neither private nor declared for subclass {cls}".format(name=name, cls=type(self).__name__))

  def version_me(setattr_func):
    def _version_set_declared_attr(self, name, value):
      if not type(self).versioning_on:
        return setattr_func(self,name,value)
      if not self.versioned:
        return setattr_func(self,name,value)
      elif (type(self).version_count > self._from) and (self._to==None):
        # dup becomes the "old" object and self the "new":
        dup = self.dup()
        dup._to = type(self).version_count
        self._from = type(self).version_count
        if self._prev:
          dup._prev = self._prev
          self._prev._next=dup
        dup._next = self
        self._prev = dup
        self.neoid = None
        # make the owners own dup, rather than self - this is under the radar of
        # version_me
        for okey in dup.belongs:
          owner = dup.belongs[okey]
          (oid,*att)=okey
          if len(att)==2:
            getattr(owner,att[0]).data[att[1]] = dup
          else:
            owner.__dict__[att[0]] = dup
        setattr_func(self,name,value) ###
        # this is on version_me's radar- dups the owning entity if nec
        for okey in self.belongs:
          owner = self.belongs[okey]
          (oid,*att)=okey
          if len(att) == 2:
            getattr(owner,att[0])[att[1]]=self 
          else:
            if att[0]=='category':
              set_trace()
            setattr(owner,att[0],self)
          if owner._prev:
            # dup (old entity) needs to belong to the prev version of owner
            del dup.belongs[ (id(owner), *att) ]
            dup.belongs[ (id(owner._prev),*att) ] = owner._prev
      else:
        return setattr_func(self,name,value)
    return _version_set_declared_attr

  @version_me
  def _set_declared_attr(self,name,value):
    atts =type(self).attspec[name]
    if atts == 'simple':
      pass
    elif atts  == 'object':
      oldval = self.__dict__.get(name)
      if oldval:
        if not self.versioned:
          del oldval.belongs[(id(self),name)]
          self.removed_entities.append( (name, oldval) )
      if isinstance(value, Entity):
        value.belongs[(id(self),name)] = self
    elif atts  == 'collection':
      if isinstance(value, dict):
        value = CollValue(value,owner=self,owner_key=name)
      if isinstance(value,list): # convert list of objs to CollValue
        d={}
        for v in value:
          d[ getattr(v,type(v).mapspec()["key"]) ] = v
        value = CollValue(d,owner=self,owner_key=name)
    else:
      raise RuntimeError("unknown attspec value '{}'".format(atts))
    self.dirty=1
    self.__dict__[name] = value
    
  def __delattr__(self, name):
    del self.__dict__[name]

  
  def _check_init(self,init):
    for att in type(self).attspec:
      if init[att]:
        self._check_value(att,init[att])
                               
  def _check_value(self,att,value):
    spec = type(self).attspec[att]
    try:
      if spec == 'simple':
        if not (isinstance(value,int) or
                isinstance(value,str) or
                isinstance(value,float) or
                isinstance(value,bool) or
                value == None):
          raise ArgError(
            "value for key '{att}' is not a simple scalar".format(att=att)
          )
      elif spec == 'object':
        if not (isinstance(value,Entity) or
                value == None):
          raise ArgError(
            "value for key '{att}' is not an Entity subclass".format(att=att)
            )
      elif spec == 'collection':
        if not (isinstance(value,(dict,list,CollValue))):
          raise AttributeError(
              "value for key '{att}' is not a dict,list, or CollValue".format(att=att)
          )
      else:
        raise ArgError("unknown attribute type '{type}' for attribute '{att}' in attspec".format(type=spec,att=att) )
    except Exception:
      raise

  def dup(self):
    return type(self)(self)

  def delete(self):
    if self.versioning_on and self.versioned:
      if type(self).version_count > self._from:
        self._to = type(self).version_count
      else:
        warn("delete - current version count {vct} is <= entity's _to attribute".format(vct=type(self).version_count))
    else:
      # unlink from other entities
      for okey in self.belongs:
        owner = self.belongs[okey]
        (oid,*att)=okey
        if len(att)==2:
          del getattr(owner,att[0])[att[1]]
        else:
          setattr(owner,att[0],None)

  def dget(self,refresh=False):
    if (type(self).object_map):
      return type(self).object_map.get(self,refresh)
    else:
      pass

  def dput(self):
    if (type(self).object_map):
      return type(self).object_map.put(self)
    else:
      pass

  def rm(self,force):
    if (type(self).object_map):
      return type(self).object_map.rm(self,force)
    else:
      pass

    
class CollValue(UserDict):
  """A UserDict for housing Entity collection attributes

  A UserDict that contains a hook for recording the Entity that
  own the value that is being set. The value is marked as belonging
  to the containing object, not this collection object.
  Also protects against adding arbitrarily typed elements to the
  collection (throws unless a value to set is an Entity)

  :param owner: Entity object of which this collection is an attribute
  :param owner_key: the attribute name of this collection on the owner

  """
  def __init__(self,init=None,*,owner,owner_key):
    self.__dict__["__owner"]=owner
    self.__dict__["__owner_key"]=owner_key
    super().__init__(init)
    
  @property
  def owner(self):
    return self.__dict__["__owner"]
  @property
  def owner_key(self):
    return self.__dict__["__owner_key"]
  def version_me(setitem_func):
    def _version_set_collvalue_item(self,name,value):
      if not self.owner.versioning_on:
        return setitem_func(self,name,value)        
      if not self.owner.versioned:
        return setitem_func(self,name,value)
      elif (Entity.version_count > self.owner._from) and (self.owner._to==None):
        pass ###....
        # dup becomes the "old" object and self the "new":
        dup = self.owner.dup()
        dup._to = Entity.version_count
        self.owner._from = Entity.version_count
        if self.owner._prev:
          dup._prev = self.owner._prev
          self.owner._prev._next=dup
        dup._next = self.owner
        self.owner._prev = dup
        self.owner.neoid = None
        # make the owners own dup, rather than self.owner
        for okey in dup.belongs:
          owner = dup.belongs[okey]
          (oid,*att)=okey
          if len(att)==2:
            getattr(owner,att[0])[att[1]] = dup
          else:
            setattr(owner,att[0],dup)
        setitem_func(self,name,value) ### 
        for okey in self.owner.belongs:
          owner = self.owner.belongs[okey]
          (oid,*att)=okey
          if len(att)==2:
            getattr(owner,att[0])[att[1]]=self.owner # this dups the owning entity if nec
          else:
            setattr(owner,att[0],self.owner)
          if owner._prev:
            # dup (old entity) needs to belong to the prev version of owner
            del dup.belongs[ (id(owner), *att) ]
            dup.belongs[ (id(owner._prev),*att) ] = owner._prev
      else:
          return setitem_func(self,name,value)
    return _version_set_collvalue_item
    
  @version_me
  def __setitem__(self, name, value):
    if not isinstance(value, Entity):
      raise ArgError("a collection-valued attribute can only accept Entity members, not '{tipe}'s".format(tipe=type(value)))
    if name in self:
      oldval = self.data.get(name)
      if oldval:
        if not self.owner.versioned:
          del oldval.belongs[(id(self.owner),self.owner_key,name)]
          self.owner.removed_entities.append( (self.owner_key, oldval) )
    value.belongs[(id(self.owner),self.owner_key,name)] = self.owner
    # smudge the owner
    self.owner.dirty = 1
    self.data[name]=value
    return
  def __getitem__(self, name):
    if not name in self.data:
      return
    if self.data[name].dirty < 0:
       self.data[name].dget()
    return self.data[name]
  def __delitem__(self,name):
    self[name]==None # trigger __setitem__
    super().__delitem__(name)
    return

