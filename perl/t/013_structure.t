use Test::More;
use lib qw'../lib ..';
use Bento::Meta::Model;

$DOCKER=0;
my $docker;

if ($DOCKER) {
  unless (eval 'require t::NeoCon; 1') {
    plan skip_all => "Docker not available for test database setup: skipping.";
  }

  $docker = t::NeoCon->new(tag => 'maj1/test-plain-db-bento-meta');
  $docker->start;

  diag "Neo4j on port ".$docker->port(7687);
  diag "HTTP on port ".$docker->port(7474);

  for (qw/ Node Property ValueSet/) {
    my $cls = "Bento::Meta::Model::$_";
    $cls->object_map($cls->map_defn, $docker->cxn);
  }
}

$Bento::Meta::Model::Entity::VERSIONING_ON=1;
$Bento::Meta::Model::Entity::VERSION_COUNT=1;

ok $n1 = Bento::Meta::Model::Node->new({handle=>'n1'}), 'n1';
ok $p1 = Bento::Meta::Model::Property->new({handle=>'p1'}), 'p1';
ok $v1 = Bento::Meta::Model::ValueSet->new({handle=>'v1', id=>'blarf'}), 'v1';


ok $n1->set_props(p1 => $p1), 'n1 -> p1';
ok $p1->set_value_set($v1), 'n1 -> p1 -> v1';

ok owns($p1, $v1, 'value_set'), 'owner of v1 is p1';
ok owns($n1, $p1, 'props', 'p1'), 'owner of p1 is n1';

$Bento::Meta::Model::Entity::VERSION_COUNT=2;

ok $v1->set_id('frelb'), 'change v1';
isnt ref($v1->_prev), 'SCALAR', 'v1 dup';
isnt ref($p1->_prev), 'SCALAR', 'and p1 dup';
isnt ref($n1->_prev), 'SCALAR', 'and n1 dup';

ok owns($p1, $v1, 'value_set'), 'owner of v1 is p1';
ok owns($n1, $p1, 'props', 'p1'), 'owner of p1 is n1';

ok owns($p1->_prev, $v1->_prev, 'value_set'), 'owner of old v1 is old p1';
ok owns($n1->_prev, $p1->_prev, 'props', 'p1'), 'owner of old p1 is old n1';

ok !owns($p1, $v1->_prev, 'value_set'), 'new p1 does not own old v1';
ok !owns($n1, $p1->_prev, 'props', 'p1'), 'new n1 does not own old p1';

$Bento::Meta::Model::Entity::VERSION_COUNT=3;

ok $p2 = Bento::Meta::Model::Property->new({handle=>'p2'}), 'p2';
ok $n1->set_props('p2' => $p2), "add p2 to n1";

isnt ref $n1->_prev->_prev, 'SCALAR', 'n1 now has 3 versions';
is ref $p1->_prev->_prev, 'SCALAR', "but p1 wasn't duplicated";
is ref $p2->_prev, 'SCALAR', 'and p2 is brand new';
is $n1->props('p2'), $p2, "there it is";
is $n1->props('p1'), $p1, "also p1 is there";
ok owns($n1, $p2, 'props', 'p2'), "new n1 owns p2";
ok owns($n1, $p1, 'props', 'p1'), "new n1 owns p1";
ok !$n1->_prev->props('p2'), "but old n1 has no p2";

if ($DOCKER) {
  for $o ($n1, $p1, $v1, $p2) {
    $thing = $o;
    while (ref $thing ne 'SCALAR') {
      $thing->put;
      $thing = $thing->_prev;
    }
  }
  $DB::single=1;
  1;
}

done_testing;

sub owns {
  my ($a, $b, $k, $kk) = @_;
  my $bk = join(':',"$a",$k,($kk ? $kk : ()));
  my $obj = $b->{pvt}{_belongs}{$bk} && ${$b->{pvt}{_belongs}{$bk}}[0];
  return $obj && ($obj == $a);
}

END {
  if ($DOCKER) {
    $docker->stop;
    $docker->rm;
  }
}
1;
