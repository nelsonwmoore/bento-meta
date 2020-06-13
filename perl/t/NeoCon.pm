package t::NeoCon;
use Log::Log4perl qw/:easy/;
use IPC::Run qw/run/;
use Carp qw/croak/;
use Neo4j::Bolt;
use strict;

my ($in,$out,$err);
my $TAG = 'maj1/test-db-bento-meta';
unless (eval 'require IO::Pty;1') {
  croak __PACKAGE__." requires IO::Pty - please install it"
}
unless (run ['docker'],\$in,\$out,\$err) {
  croak __PACKAGE__." requires docker - please install it"
}

# tag => <docker tag>
# name => <container name>
# ports => <hash of port mappings container => host>

sub new {
  my $class = shift;
  my %args = @_;
  my $self = bless \%args, $class;
  $self->{tag} //= $TAG;
  $self->{name} //= "test$$";
  $self->{ports} //= {7687 => undef, 7474 => undef};
  return $self;
}

sub error { shift->{_error} }
sub name { shift->{name} }
sub tag {shift->{tag}}
sub ports { shift->{ports} }
sub port {
  my $self = shift;
  my $port = shift;
  return unless defined $port;
  if (!$self->ports->{$port}) {
    $self->get_ports;
  }
  return $self->ports->{$port};
}

sub cxn {
  my $self = shift;
  return $self->{_cxn} if $self->{_cxn};
  return $self->{_cxn} = Neo4j::Bolt->connect("bolt://localhost:".$self->port(7687));
}

sub start {
  my $self = shift;
  my @startcmd = split / /, "docker run -d -P --name $$self{name} $$self{tag}";
  INFO "Starting docker $$self{tag} as $$self{name}";
  unless (run \@startcmd, \$in, \$out, \$err) {
    $self->{_error} = $err;
    return;
  }
  sleep 10;
  $self->get_ports;
  return 1;
}

sub get_ports {
  my $self = shift;
  run [split / /, "docker container port $$self{name}"], \$in, \$out, \$err;
  for my $port (keys %{$self->{ports}}) {
    my ($p) = grep /${port}.tcp/, split /\n/,$out;
    ($p) = $p =~ m/([0-9]+)$/;
    $self->{ports}{$port} = $p;
  }
}

sub stop {
  my $self = shift;
  INFO "Stopping docker container $$self{name}";
  unless (run [split / /,"docker kill $$self{name}"], \$in,\$out,\$err) {
    $self->{_error} = $err;
    return;
  }
  return 1;
}

sub rm {
  my $self = shift;
  INFO "Removing docker container $$self{name}";
  unless ( run [split / /, "docker rm $$self{name}"],\$in,\$out,\$err ) {
    $self->{_error} = $err;
    return;
  }
  return 1;
}
1;
