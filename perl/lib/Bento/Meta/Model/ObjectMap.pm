package Bento::Meta::Model::ObjectMap;
use Scalar::Util qw/blessed/;
use Neo4j::Cypher::Abstract qw/cypher ptn/;
use Log::Log4perl qw/:easy/;
use strict;

sub new {
  my $class = shift;
  my ($obj_class, $label) = @_;
  unless ($obj_class) {
    LOGDIE "${class}::new : require an object class (string) for arg1";
  }
  # ck obj_class
  unless (defined $label) {
    ($label) = $obj_class =~ /::([^:]+)$/;
    $label = lc $label;
  }
  my $self = bless {
    _class => $obj_class,
    _label => $label,
    _property_map => {},
    _relationship_map => {},
   }, $class;
  
  return $self;
}


sub class { shift->{_class} }
sub label { shift->{_label} }
sub pmap { shift->{_property_map} }
sub rmap { shift->{_relationship_map} }

sub property_attrs {
  return keys %{ shift->pmap }
}

sub relationship_attrs {
  return keys %{ shift->rmap }
}

sub map_simple_attr {
  my $self = shift;
  my ($attr, $property) = @_;
  # ck args
  return $self->{_property_map}{$attr} = $property;
}1;

# relationship - specify as in cypher::abstract format
# so "<:rlnship" means <-[:rlnship]-
# and  ":rlnship>" means -[:rlnship]->
# if just "rlnship", add colon and assume no dir

sub map_object_attr {
  my $self = shift;
  my ($attr, $relationship, $end_label) = @_;
  # ck args
  $relationship = ":$relationship" unless ($relationship =~ /:/);
  return $self->{_relationship_map}{$attr} = [$relationship,$end_label,0];
}1;

sub map_collection_attr {
  my $self = shift;
  my ($attr, $relationship, $end_label) = @_;
  # ck args
  $relationship = ":$relationship" unless ($relationship =~ /:/);  
  return $self->{_relationship_map}{$attr} = [$relationship, $end_label,1];
}1;

# cypher query to pull a node
sub get_q {
  my $self = shift;
  my ($obj) = @_;
  unless ( blessed $obj && $obj->isa($self->class) ) {
    LOGDIE ref($self)."::get_q : arg1 must be an object of class ".$self->class;
  }
  
  if ($obj->neoid) {
    return cypher->match('n:'.$self->label)
      ->where( { 'id(n)' => $obj->neoid })
      ->return('n');
  }
  # else, find equivalent node
  my $wh = {};
  for ($self->property_attrs) {
    $wh->{$self->pmap->{$_}} = $obj->$_;
  }
  return cypher->match('n:'.$self->label)
    ->where($wh)
    ->return('n');
}

# cypher query to pull nodes via relationship
sub get_attr_q {
  my $self = shift;
  my ($obj,$att) = @_;
  unless ( blessed $obj && $obj->isa($self->class) ) {
    LOGDIE ref($self)."::get_attr_q : arg1 must be an object of class ".$self->class;
  }
  unless ($att) {
    LOGDIE ref($self)."::get_attr_q : arg2 must be an attribute name for class ".$self->class;
  }
  # set up obj match:
  my $q = $self->get_q($obj);
  # hack Cypher::Abstract - drop the return and add a with: 
  pop @{$q->{stack}};
  $q->with('n');
  if ( grep /^$att$/, $self->property_attrs ) {
    $q->return( 'n.'.$self->pmap->{$att} );
  }
  elsif (grep /^$att$/, $self->relationship_attrs ) {
    my ($reln, $end_label, $many) = @{$self->rmap->{$att}};
    $q->match(ptn->N('n')->R($reln)->N('a:'.$end_label))->
      return('a');
    $q->limit(1) unless $many;
    return $q;
  }
  else {
    LOGDIE ref($self)."::get_attr_q : '$att' is not a registered attribute for class ".$self->class;
  }
}

# put_q
# if obj has a neoid (is 'mapped'), then overwrite the props on that node
# in the DB with the props in the obj
# if obj does not have a neoid, create a new node with the props on the object
# both stmts return the node id
sub put_q {
  my $self = shift;
  my ($obj) = @_;
  unless ( blessed $obj && $obj->isa($self->class) ) {
    LOGDIE ref($self)."::put_q : arg1 must be an object of class ".$self->class;
  }
  my $props = {};
  my @null_props;
  for ($self->property_attrs) {
    if (defined $obj->$_) {
      $props->{$self->pmap->{$_}} = $obj->$_;
    }
    else {
      push @null_props, $self->pmap->{$_};
    }
  }
  
  if ($obj->neoid) {
  # rewrite props on existing node
  # need to set props that have defined values,
  # and remove props that undefined values -
  # so 2 statements are returned
    my @stmts;
    push @stmts, cypher->match('n:'.$self->label)
      ->where({ 'id(n)' => $obj->neoid })
      ->set($props)
      ->return('id(n)');
    for (@null_props) {
      push @stmts, cypher->match('n:'.$self->label)
        ->where({ 'id(n)' => $obj->neoid })
        ->remove('n.'.$_)
        ->return('id(n)');
    }
    return @stmts;
  }
  # else, create new node with props that have defined values
  return cypher->create(ptn->N('n:'.$self->label => $props))
    ->return('id(n)');
}

# put_attr_q($obj, $attr => @values)
# - query to create relationships and end nodes corresponding
# to object- or collection-valued attributes
# returns a list, one statement per $value
# can only do this on node that already is mapped in the db (must have non-empty
# neoid() attr)
# for each obj in @values - require these all be present in db as well? Or create de novo?
# - require that they be mapped: do put_q($_) for (@values), then put_attr_q,
# if necessary
sub put_attr_q {
  my $self = shift;
  my ($obj,$att, @values) = @_;
  unless ( blessed $obj && $obj->isa($self->class) ) {
    LOGDIE ref($self)."::put_attr_q : arg1 must be an object of class ".$self->class;
  }
  unless (defined $obj->neoid) {
    LOGDIE ref($self)."::put_attr_q : arg1 must be a mapped object (attr 'neoid' must be set)";  }
  unless (@values) {
    LOGDIE ref($self)."::put_attr_q : arg2,... must be a list of endpoint objects";
  }
  if ( grep /^$att$/, $self->property_attrs ) {
    return ( cypher->match('n:'.$self->label)
      ->where({'id(n)' => $obj->neoid })
      ->set( {'n.'.$self->pmap->{$att} => $values[0]} )
      ->return('id(n)') );
  }
  elsif (grep /^$att$/, $self->relationship_attrs ) {
    my ($reln, $end_label, $many) = @{$self->rmap->{$att}};
    my @stmts;
    for my $val (@values) {
      unless (blessed $val && $val->isa('Bento::Meta::Model::Entity')) {
        LOGDIE ref($self)."::put_attr_q : arg 3,... must all be Entity objects";
      }
      unless ($val->neoid) {
        LOGDIE ref($self)."::put_attr_q : arg 3,... must all be mapped objects (all must have 'neoid' set)";
      }
      my $q = cypher->match('n:'.$self->label)
        ->where({'id(n)' => $obj->neoid })
        ->with('n')
        ->merge(ptn->N('n')->R($reln)->N('a:'.$end_label)) # expect <:> in $reln
        ->where({'id(a)' => $val->neoid})
        ->return('id(a)');
      push @stmts, $q;
      last unless $many;
    }
    return @stmts;
  }
  else {
    LOGDIE ref($self)."::put_attr_q : '$att' is not a registered attribute for class ".$self->class;
  }
}

# rm_q - remove a mapped object. if $detach is TRUE then force removal
# (i.e., use DETACH DELETE), which will also remove the relationships
# in the db.
sub rm_q {
  my $self = shift;
  my ($obj,$detach) = @_;
  unless ( blessed $obj && $obj->isa($self->class) ) {
    LOGDIE ref($self)."::rm_q : arg1 must be an object of class ".$self->class;
  }
  unless (defined $obj->neoid) {
    LOGDIE ref($self)."::rm_q : arg1 must be a mapped object (attr 'neoid' must be set)";  }
  my $q = cypher->match('n:'.$self->label)
    ->where({'id(n)' => $obj->neoid });
  if ($detach) {
    $q->detach_delete('n');
  }
  else {
    $q->delete('n');
  }
  return $q->return('id(n)');
}

# rm object, collection attributes - delete relationships only, leave end nodes
# intact
# use rm_q to remove end nodes explicitly in 
sub rm_attr_q {
  my $self = shift;
  my ($obj,$att, @values) = @_;
  unless ( blessed $obj && $obj->isa($self->class) ) {
    LOGDIE ref($self)."::rm_attr_q : arg1 must be an object of class ".$self->class;
  }
  unless (defined $obj->neoid) {
    LOGDIE ref($self)."::rm_attr_q : arg1 must be a mapped object (attr 'neoid' must be set)";  }
  if ( grep /^$att$/, $self->property_attrs ) {
    return ( cypher->match('n:'.$self->label)
               ->where({'id(n)' => $obj->neoid })
               ->remove( 'n.'.$self->pmap->{$att} )
               ->return('id(n)') );
  }
  elsif (grep /^$att$/, $self->relationship_attrs ) {
    my ($reln, $end_label, $many) = @{$self->rmap->{$att}};
    my $r_reln = $reln;
    $r_reln =~ s/:/r:/;
    my @stmts;
    if ($values[0] eq ':all') { # detach all ends
      return cypher->match(ptn->N('n:'.$self->label)
                      ->R($r_reln)->N("v:$end_label"))
        ->where({ 'id(n)' => $obj->neoid })
        ->delete('r'); # delete relationship only
    }
    for my $val (@values) {
      unless (blessed $val && $val->isa('Bento::Meta::Model::Entity')) {
        LOGDIE ref($self)."::put_attr_q : arg 3,... must all be Entity objects";
      }
      unless ($val->neoid) {
        LOGDIE ref($self)."::rm_attr_q : arg 3,... must all be mapped objects (all must have 'neoid' set)";
      }
      my $q = cypher->match(ptn->N('n:'.$self->label)
                              ->R($r_reln)->N("v:$end_label"))
        ->where({
          'id(n)' => $obj->neoid,
          'id(v)' => $val->neoid
         })
        ->delete('r') # delete relationship only
        ->return('id(v)');
      push @stmts, $q;
      last unless $many;
    }
    return @stmts;
  }
  else {
    LOGDIE ref($self)."::rm_attr_q : '$att' is not a registered attribute for class ".$self->class;
  }
}


=head1 NAME

Bento::Meta::Model::ObjectMap - interface Perl objects with Neo4j database

=head1 SYNOPSIS

  # create object map for class
  $map = Bento::Meta::Model::ObjectMap->new('Bento::Meta::Model::Node')
  # map object attributes to Neo4j model 
  #  simple attrs = properties
  for my $p (qw/handle model category/) {
    $map->map_simple_attr($p => $p);
  }
  #  object- or collection-valued attrs = relationships to other nodes
  $map->map_object_attr('concept' => '<:has_concept', 'concept');
  $map->map_collection_attr('props' => '<:has_property', 'property');

  # use the map to generate canned cypher queries

=head1 DESCRIPTION

=head1 METHODS

=over 

=item new($obj_class [ => $neo4j_node_label ])

Create new ObjectMap object for class C($obj_class). Arg is a string.
If $label is not provided, the Neo4j label that is mapped to the
object is set as the last token  in the class namespace, lower-cased.
E.g., for an object of class C<Bento::Meta::Model::Node>, the label is
'node'.

=item map_simple_attr($object_attribute => $neo4j_node_property)

=item map_object_attr($object_attribute => $neo4j_node_property)

=item map_collection_attr($object_attribute => $neo4j_node_property)

=item get_q($object)

If $object is mapped, query for the node having the object's Neo4j id.
If not mapped, query for (all) nodes having properties that match the object's
simple properties. The query returns the node (possibly multiple nodes, in the
unmapped case).

=item get_attr_q($object, $object_attribute)

For an object (matched in the same way as L</get_q>):
If the attribute named ($object_attribute) is a simple type, query the value 
of the corresponding node property. The query returns the value, if it exists.

If the attribute is object- or collection-valued, query for the set of nodes
linked by the mapped Neo4j relationship (as specified to L</map_object_attr> or
L</map_collection_attr>). The query returns one node per response row.

=item put_q($object)

If $object is mapped, overwrite the mapped node's properties with the current
value of the object's simple attributes. The query returns the mapped node's
Neo4j id.

If not mapped, create a new node according to the object's simple-valued
attributes ( => Neo4j node properties), setting the corresponding properties.
The query returns the created node's Neo4j id.

=item put_attr_q($object, $object_attribute => @values)

The $object must be mapped (have a Neo4j id) for L</put_attr_q>. 
$object_attribute is the string name of the attribute (not the Neo4j property).
If the attribute is simple-valued, the third argument should be the string or 
numeric value to set. The query will set the property of the mapped node, and 
return the node id.

If the attribute is object- or collection-valued, the @values should be a list
of objects appropriate for the attribute definitions. The query will match the
object node-attribute relationship-attribute node links, and merge the attribute nodes. That is, the attribute nodes will be created if the relationship and 
matching node do not already exist. For a collection-valued attribute, one query
will be created per attribute node. Each query will return the attribute node's
Neo4j id.

=item rm_q($object, [$force])

The $object must be mapped (have a Neo4j id). The query will attempt to delete 
the mapped node from the database. If $force is false or missing, the query will
be formulated with "DELETE"; it will succeed only if the node is not participating in any relationship. 

If $force is true, the query will be formulated with "DETACH DELETE", and the executed query will remove the mapped node and all relationships in which it
participates.

=item rm_attr_q($object, $object_attribute => @values)



=back

=head1 AUTHOR

 Mark A. Jensen < mark -dot- jensen -at- nih -dot- gov >
 FNL

=cut

1;
