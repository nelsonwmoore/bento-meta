package Bento::Meta::Model::Edge;
use base Bento::Meta::Model::Entity;
use Log::Log4perl qw/:easy/;
use strict;

# one edge per type:src:dst triplet
sub new {
  my $class = shift;
  my ($init) = @_;
  my $self =  $class->SUPER::new({
    _handle => undef,
    _model => undef,
    _multiplicity => undef,
    _src => \undef,
    _dst => \undef,
    _is_required => undef,
    _type => undef,
    _concept => \undef,
    _tags => [],
    _props => {}, # prop | edge has_property prop (key: prop.handle)
  }, $init);

  return $self;
}

sub cardinality { shift->multiplicity(@_) }
sub triplet {
  my $self = shift;
  return $self->{_triplet} //
    ($self->{_triplet} = join(':',$self->handle,
                             $self->src->handle,
                             $self->dst->handle));
}

sub map_defn {
  return {
    label => 'relationship',
    simple => [
      [handle => 'handle'],
      [model => 'model'],
      [type => 'neo_type'],
      [multiplicity => 'multiplicity'],
      [is_required => 'is_required'],
     ],
    object => [
      [ src => ':has_src>',
        'Bento::Meta::Model::Node' => 'node' ],
      [ dst => ':has_dst>',
        'Bento::Meta::Model::Node' => 'node' ],
      [ concept => ':has_concept>',
        'Bento::Meta::Model::Concept' => 'concept']
     ],
    collection => [
      [ props => ':has_property>',
        'Bento::Meta::Model::Property' => 'property' ],
     ]
   };
}

=head1 NAME

Bento::Meta::Model::Edge - object that models an egde or relationship

=head1 SYNOPSIS

=head1 DESCRIPTION

=head1 METHODS

=over

=item multiplicity(), cardinality()

Whether the edge from src to dst is one_to_one, one_to_many, many_to_one, or
many_to_many.

=item triplet()

This is a string giving the edge type, source node label, and destination 
node label, separated by colons. 

 print $edge->triplet; # of_case:diagnosis:case

Helpful for finding a particular edge.

 $diag_to_case = grep { $_->triplet eq 'of_case:diagnosis:case' } $model->edges;

=back

=head1 AUTHOR

 Mark A. Jensen < mark -dot- jensen -at- nih -dot- gov >
 FNL

=cut

1;
