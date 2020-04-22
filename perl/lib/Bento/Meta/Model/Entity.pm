package Bento::Meta::Model::Entity;
use Bento::Meta::Model::ObjectMap;
use UUID::Tiny qw/:std/;
use Log::Log4perl qw/:easy/;

use strict;
our $OBJECT_MAP;
our $AUTOLOAD;

our @private_attr = qw/
_dirty
_neoid
                     /;
sub new {
  my $class = shift;
  my ($attr,$init) = @_;
  my $self = bless $attr, $class;
  $self->{pvt}{_dirty} = 1; # indicates change that has not been synced with db
  #                      0 => fully synced with db
  #                     -1 => simple-valued attr sync, object-valued attr not yet
  $self->{pvt}{_neoid} = undef; # database id for this entity
  $self->{_desc} = undef; # free text description for entity

  my @declared_atts = map { my ($a)=/^_(.*)/;$a || () } keys %$self;
  $self->{_declared} = \@declared_atts;

  if (defined $init) {
    unless (ref($init) =~ /^HASH|Neo4j::Bolt::Node$/) {
      LOGDIE "${class}::new - arg1 must be a Neo4j::Bolt::Node or hashref of initial attr values";
    }
    return $self->set_with_node($init) if (ref($init) eq 'Neo4j::Bolt::Node');
    # else, a plain hashref
    for my $k (keys %$init) {
      if (grep /^$k$/, @declared_atts) {
        my $set = "set_$k";
        $self->$set($init->{$k});
      }
      else {
        LOGWARN "${class}::new() - attribute '$k' in init not declared in object";
        $self->{"_$k"} = $init->{$k};
      }
    }
  }
  return $self;
}

# add an object map to the (subclassed) object
# and attach get, put as available methods to instances
sub object_map {
  my $class = shift;
  unless (!ref $class) {
    LOGDIE __PACKAGE__."::object_map : class method only";
  }
  my ($map, $bolt_cxn) = @_;
  my $omap = eval "\$${class}::OBJECT_MAP;";
  return $omap if defined $omap;

  $omap = Bento::Meta::Model::ObjectMap->new($class, $map->{label}, $bolt_cxn);
  for (@{$map->{simple}}) {
    $omap->map_simple_attr(@$_);
  }
  for (@{$map->{object}}) {
    $omap->map_object_attr(@$_);
  }
  for (@{$map->{collection}}) {
    $omap->map_collection_attr(@$_);
  }
  eval qq|
  \$${class}::OBJECT_MAP = \$omap
|;
  eval qq|
 *${class}::get = sub { \$${class}::OBJECT_MAP->get( shift, \@_ ) };
 *${class}::put = sub { \$${class}::OBJECT_MAP->put( shift, \@_ ) };
 *${class}::rm = sub { \$${class}::OBJECT_MAP->rm( shift, \@_ ) };
 *${class}::put_q = sub { \$${class}::OBJECT_MAP->put_q( shift, \@_ ) };
 *${class}::add = sub { \$${class}::OBJECT_MAP->add( shift, \@_ ) };
 *${class}::drop = sub { \$${class}::OBJECT_MAP->drop( shift, \@_ ) };
|;
  return $omap;
}

# any object can poop a uuid if needed
sub make_uuid { create_uuid_as_string(UUID_V4) };

sub AUTOLOAD {
  my $self = shift;
  my $class = ref $self;
  my @args = @_;
  my $method = $AUTOLOAD =~ s/.*:://r;
  my ($action) = $method =~ /^([^_]+)_/;
  if ($action) {
    if (grep /^$action$/, qw/set add drop/) {
      $method =~ s/^${action}_//;
    }
    else {
      undef $action;
    }
  }
  if (grep /^$method$/, @{$self->{_declared}}) {
    my $att = $self->{"_$method"};
    if (!$action) { # getter
      for (ref $att) {
        /^ARRAY$/ && do {
          return @$att;
        };
        /^HASH$/ && do {
          if ($args[0]) {
            return $att->{$args[0]};
          }
          else {
            return wantarray ? values %$att : $att;
          }
        };
        /^SCALAR$/ && do {
          return $$att; # this picks up \undef (unset object property) and returns false
        };
        do {
          return $att;
        };
      }
    }
    elsif ($action eq 'set') { #setter
      return unless @args;
      for (ref $att) {
        /^ARRAY$/ && do {
          unless (ref $args[0] eq 'ARRAY') {
            LOGDIE "set_$method requires arrayref as arg1";
          }
          $self->{pvt}{_dirty} = 1;
          return $self->{"_$method"} = $args[0];
        };
        /^HASH$/ && do {
          if (ref $args[0] eq 'HASH') {
            $self->{pvt}{_dirty} = 1;
            return $self->{"_$method"} = $args[0];
          }
          elsif (!ref($args[0]) && @args > 1) {
            $self->{pvt}{_dirty} = 1;
            if (defined $args[1]) {
              return $self->{"_$method"}{$args[0]} = $args[1];
            }
            else { # 2nd arg is explicit undef - means delete
              return delete $self->{"_$method"}{$args[0]}
            }
          }
          else {
            LOGDIE "set_$method requires hashref as arg1, or key => value as arg1 and arg2";
          }
        };
        do { # scalar attribute
          $self->{pvt}{_dirty} = 1;
          if ($args[0]) {
            return $self->{"_$method"} = $args[0];
          }
          else {
            # handle clearing an object attribute
            $self->{"_$method"} = ref($self->{"_$method"}) ? \undef : undef;
            return undef;
          }
        };
      }
    }
    elsif ($action eq 'add') {
      return unless $class->object_map;
      unless ($self->atype($method) =~ /ARRAY|HASH/) {
        LOGWARN ref($self)."::add_$method - add action not relevant for this attribute";
        return;
      }
      return $self->add($method, $args[0]);
    }
    elsif ($action eq 'drop') {
      return unless $class->object_map;
      unless ($self->atype($method) =~ /ARRAY|HASH/) {
        LOGWARN ref($self)."::drop_$method - drop action not relevant for this attribute";
        return;
      }
      return $self->drop($method, $args[0]);
    }
    else {
      LOGDIE "Method action '$action' unknown for ".ref($self);
    }
  }
  else {
    LOGDIE "Method '$method' undefined for ".ref($self);
  }
}

sub attrs { @{shift->{_declared}} }
sub atype { ref shift->{"_".shift} }
sub name { shift->{_handle} }
sub neoid { shift->{pvt}{_neoid} }
sub set_neoid { $_[0]->{pvt}{_neoid} = $_[1] }
sub dirty { shift->{pvt}{_dirty} }
sub set_dirty { $_[0]->{pvt}{_dirty} = $_[1] }
sub map_defn { LOGWARN ref(shift)."::map_defn - subclass method; not defined for base class"; return; }

sub set_with_node {
  my $self = shift;
  my ($node) = @_;
  unless (ref($node) eq 'Neo4j::Bolt::Node') {
    LOGDIE ref($self)."::set_with_node : arg1 must be a Neo4j::Bolt::Node";
  }
  # note: if property is not present in node, set_with_node will
  # undef the corresponding attribute. 
  for (grep { !$self->atype($_) } $self->attrs) { # only scalar attrs
    my $set = "set_$_";
    $self->$set($node->{properties}{$_});
  }
  $self->set_neoid($node->{id});
  return $self;
}

sub DESTROY {
  my $self = shift;
  for (keys %$self) {
    undef $self->{$_};
  }
  return;
}

=head1 NAME

Bento::Meta::Model::Entity - base class for model objects

=head1 SYNOPSIS

 package Bento::Meta::Model::Object;
 use base Bento::Meta::Model::Entity;
 use strict;
 
 sub new {
   my $class = shift;
   my ($init_hash) = @_;
   my $self = $class->SUPER::new( {
     _my_scalar_attr => undef,
     _my_object_attr => \undef,
     _my_array_attr => [],
     _my_hash_attr => {},
     }, $init );
 }

 use Bento::Meta::Model::Object;
 $o = Bento::Meta::Model::Object->new({
  my_scalar_attr => 1,
  my_array_attr => [qw/ a b c /],
  my_object_attr => $Object,
  my_hash_attr => { yet => 0, another => 1, hashref => 2},
 });

 # getters
 $value = $o->my_scalar_attr;  # get scalar value
 @values = $o->my_array_attr;  # get array (not ref)
 $hash_value = $o->my_hash_attr; # get hashref, but prefer this:
 $value_for_key = $o->my_hash_attr( $key ); # get hash value for key, or
 @hash_values = $o->my_hash_attr; # in array context, returns hash values as array

 # setters
 $new_value = $o->set_my_scalar_attr("new value!"); # set scalar
 $o->set_my_array_attr( [ qw/ arrayref with some values / ] ); # replace arrayref
 $o->set_my_hash_attr( key => $value ); # set a value for a key in hash attr
 $o->set_my_hash_attr( { brand => 1, new => 2, hashref => 3 }); # replace hashref 

=head1 DESCRIPTION

Bento::Meta::Model::Entity is a base class that allows quick and dirty setup
of model objects and provides a consistent interface to simple attributes.
See L</SYNOPSIS>.

It also provides a place for common actions that must occur for OGM bookkeeping.

You can override anything in the subclasses and make them as complicated as 
you want. 

Private (undeclared) common attributes do not appear in the $obj->attrs. 
The base class Entity has the following private attributes

 neoid - the Neo4j internal id integer for the node mapped to the object 
         (if any)
 dirty - a flag that is set when the object has been changed but not yet pushed
         to the database


=head1 METHODS


=head2 Class Methods

=over

=item new($attr_hash, $init_hash)

$attr_hash configures the object's declared attributes. $init_hash
initializes the attributes' values. $init_hash can be a plain hashref
or a L<Neo4j::Bolt::Node>.

=item object_map($map_definition_hashref, $bolt_cxn), object_map() - getter

Create and attach an L<Bento::Meta::Model::ObjectMap> to the C<Entity> subclass.
The ObjectMap defines the associations from the object class and 
attributes to the Neo4j graph model, as well as the connection to the graph
database. When the ObjectMap is defined, instances receive the L</get()>,
L</put()>, L<add_E<lt>attrE<gt>>, and L<drop_E<lt>attrE<gt>> methods for
maintaining consistency between objects and nodes in the graph.

For a given subclass of C<Entity>, the map definition hash provides the 
corresponding label for its mapped Neo4j node, the mappings of simple scalar
attributes to mapped node properties, object-valued attributes to the mapped 
Neo4j relationship and target node, and collection-valued attributes to their
mapped relationship and target nodes. Example:

 my $omap = "Bento::Meta::Model::Node"->object_map(
    {
      label => 'node',
      simple => [
        [model => 'model'],
        [handle => 'handle']
       ],
      object => [
        [ 'concept' => ':has_concept>',
          'Bento::Meta::Model::Concept' => 'concept' ],
       ],
      collection => [
        [ 'props' => ':has_property>',
          'Bento::Meta::Model::Property' => 'property' ],
       ]
     },
     $bolt_cxn
   );

Note that each individual attribute map is an arrayref with a single element,
and that these are wrapped in another arrayref which is assigned to the 
relevant hash key.

The simple-valued attribute maps have this form:

 [ <attribute_name> => <neo4j_property_name> ]

The object-valued attribute maps have this form:

 [ <attribute_name> => <neo4j_relationship_type>,
   <target_attribute_classname> => <neo4j_target_node_label> ]

The directionality of the relationship is given using an angle bracket, 
as in L<Neo4j::Cypher::Abstract>. The direction is given relative to the the 
subclass.

The database connection of the map can set in the setter or on the map object:

 $cxn = Neo4j::Bolt->connect("bolt://localhost:7687");
 $omap->bolt_cxn($cxn);

=back

=head2 Instance Methods

=over

=item make_uuid()

Create a new uuid (with L<Data::UUID>).
Doesn't put it anywhere, just returns it.

=item attrs()

Returns list of attributes declared for this object. 

=item atype($attr)

Return type of the attribute $attr.
  undef => scalar
 'SCALAR' or ref($obj) => object
 'ARRAY' => array, 
 'HASH' => hash

=item set_with_node($neo4j_bolt_node)

Set all simple scalar attributes according to values in 
$neo4j_bolt_node-E<gt>{properties}.

=item map_defn()

This should be defined in the subclasses. It should return a map definition 
hashref for the subclass as described above in L</object_map>.

=back

=head2 Database interaction methods

When the subclass has been instrumented with an L<Bento::Meta::Model::ObjectMap>,
the following methods are available on any instance.

=over

=item get()

=item put()

=item rm()

=item add_<attr>()

=item drop_<attr>()

=back

=head1 AUTHOR

 Mark A. Jensen (mark -dot- jensen -at- nih -dot- gov)
 FNL

=cut




1;
