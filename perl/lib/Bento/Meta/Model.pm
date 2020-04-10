package Bento::Meta::Model;
use base Bento::Meta::Model::Entity;
use v5.10;
use Scalar::Util qw/blessed/;
use lib '../../../lib';
use Bento::Meta::Model::Node;
use Bento::Meta::Model::Edge;
use Bento::Meta::Model::Property;
use Bento::Meta::Model::ValueSet;
use Bento::Meta::Model::Origin;
use Bento::Meta::Model::Concept;
use Bento::Meta::Model::Term;
use Carp qw/croak/;
use Log::Log4perl qw/:easy/;
use strict;

# new($handle)
sub new {
  my $class = shift;
  my ($handle) = @_;
  unless ($handle) {
    LOGDIE "Model::new() requires handle as arg1";
  }
  DEBUG "Creating Model object with handle '$handle'";
  my $self = $class->SUPER::new({
    _handle => $handle,
    _nodes => {},
    _edges => {},
    _props => {},
    _edge_table => {},
   });
  return $self;
}

# create/delete API

# add_node( {handle =>'newnode', ...} ) or add_node($node)
# new node will be added to the Model nodes hash
sub add_node {
  my $self = shift;
  my ($init) = shift;
  if (ref($init) eq 'HASH') {
    $init = Bento::Meta::Model::Node->new($init);
  }
  unless ($init->handle) {
    LOGDIE ref($self)."::add_node - init hash reqs 'handle' key/value";
  }
  if (defined $self->node($init->handle)) {
    LOGWARN ref($self)."::add_node : overwriting existing node with handle '".$init->handle."'";
  }
  $init->set_model($self->handle) if (!$init->model);
  if ($init->model ne $self->handle) {
    LOGWARN ref($self)."::add_node : model handle is '".$self->handle."', but node.model is '".$init->model."'";
  }
  for my $p ($init->props) { # add any props on this node to the model list
    $p->set_parent_handle($init->handle);
    $p->set_model($self->handle);
    $self->set_props(join(':',$init->handle,$p->handle) => $p);
  }
  $self->set_nodes($init->handle, $init);
}

# add_edge( { handle => 'newreln', src => $from_node, dst => $to_node, ... })
# or add_edge( $edge )
# note: the Edge obj created will always have src and dst attribs that
# are Node objects, and that appear in the Model node hash
# if node or node handle does not appear in Node,it will be added (with add_node)

sub add_edge {
  my $self = shift;
  my ($init) = shift;
  my $etbl = $self->{_edge_table};
  if (ref($init) eq 'HASH') {
    $init = Bento::Meta::Model::Edge->new($init);
  }
  unless ( $init->handle && $init->src && $init->dst ) {
    LOGDIE ref($self)."::add_edge - init hash reqs 'handle','src','dst' key/values";
  }
  $init->set_model($self->handle) if (!$init->model);
  my ($hdl,$src,$dst) = split /:/,$init->triplet;
  if ($etbl->{$hdl} && $etbl->{$hdl}{$src} &&
        $etbl->{$hdl}{$src}{$dst}) {
    LOGWARN ref($self)."::add_edge : overwriting existing edge with handle/src/dest '".join("/",$hdl,$src,$dst)."'";
  }
  unless ($self->contains($init->src)) {
    LOGWARN ref($self)."::add_edge : source node '".$src."' is not yet in model, adding it";
    $self->add_node($init->src);
  }
  unless ($self->contains($init->dst)) {
    LOGWARN ref($self)."::add_edge : destination node '".$dst."' is not yet in model, adding it";
    $self->add_node($init->dst);
  }
  $etbl->{$hdl}{$src}{$dst} = $init;
  for my $p ($init->props) { # add any props on this edge to the model list
    $p->set_parent_handle($init->triplet);
    $p->set_model($self->handle);
    $self->set_props(join(':',$init->triplet,$p->handle) => $p);
  }
  $self->set_edges( $init->triplet => $init );
}

# add_prop( $node | $edge, {handle => 'newprop',...})
# new Property obj will be recorded in the Model props hash
# Prop object will be added to Node object existing in the Model nodes hash
# if node or edge does not appear in Node list, it will be added (with add_node
# or add_edge)
# require node or edge objects to exist - 

sub add_prop {
  my $self = shift;
  my ($ent, $init) = @_;
  unless ( ref($ent) =~ /Node|Edge$/ ) {
    LOGDIE ref($self)."::add_prop - arg1 must be Node or Edge object";
  }
  unless (defined $init) {
    LOGDIE ref($self)."::add_prop - arg2 must be init hash or Property object";
  }
  unless ($self->contains($ent)) {
    my ($thing) = ref($ent) =~ /::([^:]+)$/;
    $thing = lc $thing;
    my $thing_method = "add_$thing";
    LOGWARN ref($self)."::add_prop : $thing '".$ent->handle."' is not yet in model, adding it";
    $self->$thing_method($ent);
  }
  if (ref($init) eq 'HASH') {
    $init = Bento::Meta::Model::Property->new($init);
  }
  unless ($init->handle) {
    LOGDIE ref($self)."::add_prop - init hash (arg2) reqs 'handle' key/value";
  }
  $init->set_model($self->handle) if (!$init->model);
  my $pfx = $ent->can('triplet') ? $ent->triplet : $ent->handle;
  $init->set_parent_handle($pfx); # "whom do I belong to?"
  if ( $self->prop(join(':',$pfx,$init->handle)) ) {
    LOGWARN ref($self)."::add_prop - overwriting existing prop '".join(':',$pfx,$init->handle)."'";
  }
  $ent->set_props( $init->handle => $init );
  $self->set_props( join(':',$pfx,$init->handle) => $init );
}

# add_terms($property, @terms_or_strings)
# $property - Property object
# @terms_or_strings - Terms objects or strings representing acceptable values
# warn and return if property doesn't have value_domain eq 'value_set'
# attach Terms to the property's ValueSet obj
# create a ValueSet objects if one doesn't exist
# create Term objects for plain strings
# returns the ValueSet object

sub add_terms {
  my $self = shift;
  my ($prop, @terms) = @_;
  unless (ref($prop) =~ /Property$/) {
    LOGDIE ref($self)."::add_terms : arg1 must be Property object";
  }
  unless (@terms) {
    LOGDIE ref($self)."::add_terms : arg2,... required (strings and/or Term objects";
  }
  $prop->value_domain // $prop->set_value_domain('value_set');
  unless ($prop->value_domain eq 'value_set') {
    LOGWARN ref($self)."::add_terms : property '".$prop->handle."' has value domain '".$prop->value_domain."', not 'value_set'";
    return;
  }
  my %terms;
  for (@terms) {
    if (ref =~ /Term$/) {
      $terms{$_->value} = $_;
      next;
    }
    elsif (!ref) {
      $terms{$_} = Bento::Meta::Model::Term->new({value => $_});
    }
    else {
      LOGDIE ref($self)."::add_terms : arg2,... must be strings or Term objects";
    }
  }
  my $vs = $prop->value_set;
  unless ($vs) {
    $vs = Bento::Meta::Model::ValueSet->new();
    $vs->set_id( $vs->make_uuid );
    $vs->set_handle( $self->handle.substr($vs->id,0,7) );
    $prop->set_value_set($vs)
  }
  $vs->set_terms($_ => $terms{$_}) for keys %terms;
  return $vs;
}

# rm_node( $node_or_handle )
# node must participate in no edges to be able to be removed (like neo4j)
# returns the node removed
# removes the node's properties from the model list, but not
# from the node itself
sub rm_node {
  my $self = shift;
  my ($node) = @_;
  unless (ref($node) =~ /Node$/) {
    LOGDIE ref($self)."::rm_node - arg1 must be Node object";
  }
  if (!$self->contains($node)) {
    LOGWARN ref($self)."::rm_node : node '".$node->handle."' not contained in model '".$self->handle."'";
    return;
  }
  if ( $self->edges_by_src($node) ||
         $self->edge_by_dst($node) ) {
    LOGWARN ref($self)."::rm_node : can't remove node '".$node->handle."', it is participating in edges";
    return;
  }
  # remove node properties from the model list
  for my $p ($node->props) {
    # note, this only removes from the model list --
    # the prop list for the node itself is not affected
    # (i.e., the props remain attached to the deleted node)
    $self->set_props(join(':',$p->parent_handle,$p->handle) => undef);
  }
  return $self->set_nodes( $node->handle => undef );
}

# rm_edge( $edge_or_sth_else )
# returns the edge removed from the model list
# removes the edge's properties from the model list, but not
# from the edge itself
sub rm_edge {
  my $self = shift;
  my ($edge) = @_;
  unless (ref($edge) =~ /Edge$/) {
    LOGDIE ref($self)."::rm_edge - arg1 must be Edge object";
  }
  if (!$self->contains($edge)) {
    LOGWARN ref($self)."::rm_edge : edge '".$edge->triplet."' not contained in model '".$self->handle."'";
    return;
  }
  # remove node properties from the model list
  for my $p ($edge->props) {
    # note, this only removes props from the model list --
    # the prop list for the edge itself is not affected
    # (i.e., the props remain attached to the deleted edge)
    $self->set_props(join(':',$p->parent_handle,$p->handle) => undef);
  }
  my ($hdl,$src,$dst) = split /:/, $edge->triplet;
  delete $self->{_edge_table}{$hdl}{$src}{$dst};
  return $self->set_edges( $edge->triplet => undef );
}

# rm_prop( $prop_or_handle )
# removes the property from the entity (node, edge) that has it,
# and from the model property list
# returns the prop removed
sub rm_prop {
  my $self = shift;
  my ($prop) = @_;
  unless (ref($prop) =~ /Property$/) {
    LOGDIE ref($self)."::rm_prop - arg1 must be Property object";
  }
  if (!$self->contains($prop)) {
    LOGWARN ref($self)."::rm_prop : property '".$prop->handle."' not contained in model '".$self->handle."'";
    return;
  }
  # following is sort of a kludge - depends on the $prop->parent_handle
  # to determine the affected entity. Faster than searching all props over
  # all entities to find the affected entity.
  if ($prop->parent_handle =~ /:/) { # an edge prop
    $self->edge($prop->parent_handle)->set_props( $prop->handle => undef );
  }
  else { # a node prop
    $self->node($prop->parent_handle)->set_props( $prop->handle => undef );
  }
  return $self->prop( join(':',$prop->parent_handle,$prop->handle) => undef );
}

# contains($entity) - true if entity object appears in model
sub contains {
  my $self = shift;
  my ($ent) = @_;
  unless ( blessed($ent) && $ent->isa('Bento::Meta::Model::Entity') ) {
    LOGWARN ref($self)."::contains - arg not an Entity object";
    return;
  }
  for (ref $ent) {
    /Node$/ && do {
      return !! grep { $_ == $ent } $self->nodes;
      last;
    };
    /Edge$/ && do {
      return !! grep { $_ == $ent } $self->edges;      
      last;
    };
    /Property$/ && do {
      return !! grep { $_ == $ent } $self->props;      
      last;
    };
    /ValueSet$/ && do {
      last;
    };
    /Term$/ && do {
      last;
    };
    /Concept$/ && do {
      last;
    };
  }
  return;
}

# read API

sub node { $_[0]->{_nodes}{$_[1]} }
sub nodes { values %{shift->{_nodes}} }

sub prop { $_[0]->{_props}{$_[1]} }
sub props { values %{shift->{_props}} }

#sub edge_types { values %{shift->{_edge_types}} }
#sub edge_type { $_[0]->{_edge_types}{$_[1]} }

sub edges { values %{shift->{_edges}} }
sub edge {
  my $self = shift;
  my ($type,$src,$dst) = @_;
  if ($type =~ /:/) { # triplet
    ($type,$src,$dst) = split /:/,$type;
  }
  else {
    $type = $type->name if ref $type;
    $src = $src->name if ref $src;
    $dst = $dst->name if ref $dst;
  }
  return $self->{_edge_table}{$type}{$src}{$dst};
}

sub edge_by_src { shift->edges_by_src(@_) }
sub edge_by_dst { shift->edges_by_dst(@_) }
sub edge_by_type { shift->edges_by_type(@_) }

sub edges_by_src { shift->edge_by('src',@_) }
sub edges_by_dst { shift->edge_by('dst',@_) }
sub edges_by_type { shift->edge_by('type',@_) }

sub edge_by {
  my $self = shift;
  my ($key, $arg) = @_;
  unless ($key =~ /^src|dst|type$/) {
    LOGDIE ref($self)."::edge_by : arg 1 must be one of src|dst|type";
  }
  if (ref($arg) =~ /Model/) {
    $arg = $arg->handle;
  }
  elsif (ref $arg) {
    LOGDIE ref($self)."::edge_by : arg must be a ".__PACKAGE__."-related object or string, not ".ref($arg);
  }
  my @ret;
  for ($key) {
    /^src$/ && do {
      for my $t (keys %{$self->{_edge_table}}) {
        for my $u (keys %{$self->{_edge_table}{$t}{$arg}}) {
          push @ret, $self->{_edge_table}{$t}{$arg}{$u} // ();
        }
      }
      last;
    };
    /^dst$/ && do {
      for my $t (keys %{$self->{_edge_table}}) {
        for my $u (keys %{$self->{_edge_table}{$t}}) {
          push @ret, $self->{_edge_table}{$t}{$u}{$arg} // ();
        }
      }
      last;
    };
    /^type$/ && do {
      for my $t (keys %{$self->{_edge_table}{$arg}}) {
        for my $u (keys %{$self->{_edge_table}{$arg}{$t}}) {
          push @ret, $self->{_edge_table}{$arg}{$t}{$u} // ();
        }
      }
      last;
    };
  }
  return @ret;
}
1;

=head1 NAME

Bento::Meta::Model - object bindings for Bento Metamodel DB

=head1 SYNOPSIS

$model = Bento::Meta::Model->new();

=head1 DESCRIPTION

=head1 METHODS

=head2 $model object

=over

=item @nodes = $model->nodes()

=item $node = $model->node($name)

=item @props = $model->props()

=item $prop = $model->prop($name)

=item $edge_type = $model->edge_type($type)

=item @edge_types = $model->edge_types()

=item @edges = $model->edge_by_src()

=item @edges = $model->edge_by_dst()

=item @edges = $model->edge_by_type()

=back

=head2 $node object

=over


=item $node->name()

=item $node->category()

=item @props = $node->props()

=item $prop = $node->prop($name)

=item @tags = $node->tags()

=back

=head2 $prop object

=over

=item $prop->name()

=item $prop->is_required()

=item $value_type = $prop->type()

=item @acceptable_values = $prop->values()

=item @tags = $prop->tags()

=back

=head2 $edge_type object

=over

=item $edge_type->name()

=item $edge_type->multiplicity(), $edge_type->cardinality()

=item $prop = $edge_type->prop($name)

=item @props = $edge_type->props()

=item @allowed_ends = $edge_type->ends()

=item @tags = $edge_type->tags()

=back

=head2 $edge object

=over

=item $edge->type()

=item $edge->name()

=item $edge->is_required()

=item $node = $edge->src()

=item $node = $edge->dst()

=item @props = $edge->props()

=item $prop = $edge->prop($name)

=item @tags = $edge->tags()

=back

=cut

1;
