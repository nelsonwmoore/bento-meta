package Bento::Meta::Model::Property;
use base Bento::Meta::Model::Entity;
use Log::Log4perl qw/:easy/;
use strict;

sub new {
  my $class = shift;
  my ($init) = @_;
  my $self = $class->SUPER::new( {
    _handle => undef,
    _model => undef,
    _value_domain => undef,
    _units => undef,
    _pattern => undef,
    _is_required => undef,
    _value_set => \undef, # prop has_value_set value_set
    _entities => {}, # entity | entity has_property prop
    _tags => [],
    _propdef => {}
   }, $init );
  return $self;
}

sub map_defn {
  return {
    label => 'property',
    simple => [
      [handle => 'handle'],
      [model => 'model'],
      [value_domain => 'value_domain'],
      [is_required => 'is_required'],
      [units => 'units'],
      [pattern => 'pattern'],
     ],
    object => [
      [ 'value_set' => ':has_value_set>',
        'Bento::Meta::Model::ValueSet' => 'value_set' ],
     ],
    collection => [
      [ 'entities' => '<:has_property',
        ['Bento::Meta::Model::Node',
         'Bento::Meta::Model::Edge'] => ''],
      ]
   };
}

sub type { shift->{_value_domain} } # alias
sub values {
  my $self = shift;
  return unless $self->value_set;
  my @ret;
  for ($self->value_set->terms) {
    push @ret, $_->value;
  }
  return @ret;
}

sub terms {
  my $self = shift;
  return unless $self->value_set;
  return $self->value_set->terms(@_);
}

sub set_terms {
  my $self = shift;
  return unless $self->value_set;
  return $self->value_set->set_terms(@_);
}

=head1 NAME

Bento::Meta::Model::Property - object that models a node or relationship property

=head1 SYNOPSIS

=head1 DESCRIPTION

=head1 METHODS

=head1 AUTHOR

 Mark A. Jensen < mark -dot- jensen -at- nih -dot- gov >
 FNL

=cut

1;
