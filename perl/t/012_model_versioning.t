use Test::More;
use Test::Exception;
use Test::Warn;
use lib qw'../lib ..';
use Log::Log4perl qw/:easy/;
use Bento::Meta::Model;
use Neo4j::Bolt;
use strict;

Log::Log4perl->easy_init($WARN);
our $B = 'Bento::Meta::Model';
our $N = "${B}::Node";
our $E = "${B}::Edge";
our $V = "${B}::ValueSet";
our $T = "${B}::Term";
our $P = "${B}::Property";

unless (eval 'require t::NeoCon; 1') {
  plan skip_all => "Docker not available for test database setup: skipping.";
}

my $docker = t::NeoCon->new(tag => 'maj1/test-plain-db-bento-meta');
$docker->start;
my $port = $docker->port(7687);
diag "Neo4j on port $port";
diag "HTTP on port ".$docker->port(7474);

ok my $model = Bento::Meta::Model->new('test'), "model inst";
$model->set_bolt_cxn( Neo4j::Bolt->connect("bolt://localhost:$port") );



$model->versioning(1);
$model->version_count(1);

diag "Build versioned model";

#         r1
#       /   \
#    n1       n2
#            /|\
#          p1 p2 p3
my ($n1,$n2,$r1,$p1,$p2,$p3);

ok $n1 = $N->new({handle=>'n1'});
ok $n2 = $N->new({handle=>'n2'});
ok $r1 = $E->new({handle=>'r1', src => $n1, dst => $n2});
ok $p1 = $P->new({handle=>'p1'});
ok $p2 = $P->new({handle=>'p2'});
ok $p3 = $P->new({handle=>'p3'});

ok $model->add_node($n1);
ok $model->add_node($n2);
ok $model->add_edge($r1);
ok $model->add_prop( $n2 => $p1 );
ok $model->add_prop( $n2 => $p2 );
ok $model->add_prop( $n2 => $p3 );

#ok $model->put,'put';
$DB::single=1;
diag "http://localhost:".$docker->port(7474);
diag "bolt://localhost:$port";


1;

#         r1       r21
#       /   \    /    \
#    n1       n2       n21
#            /|\        |
#          p1 p2 p3    p21

is $model->version_count(2), 2, "bump up version";

my ($r21,$n21,$p21);
ok $n21 = $N->new({handle=>'n21'});
ok $r21 = $E->new({handle=>'r21', src => $n2, dst => $n21});
ok $p21 = $P->new({handle=>'p21'});

ok $model->add_node($n21);
ok $model->add_edge($r21);
ok $model->add_prop( $n21 => $p21 );

#ok $model->put, 'put';
$DB::single=1;
1;

#         r1       r21 ------
#       /   \    /            \
#    n1*      n2      XXn21XX  n31
#            /|\              /
#          p1 p2 p3    p21---

is $model->version_count(3), 3, "bump version count";

my ($n31);

ok $n31 = $N->new({handle => 'n31'});
ok $model->add_node($n31);

ok $model->assign_edge_end($r21, 'dst' => $n31 ), 'reassign edge dst so I can...';
ok $model->rm_node($n21), "del n21";

is $r21->dst, $n31, "connected";
ok $r21->_prev, "prev version n31 exists";

is $r21->_prev->dst, $n21, "prev version still linked to n21";

ok $model->add_prop($n31 => $p21);

ok $model->node('n1')->set_category('blarf'), "set a scalar attribute (generates dup)";
is $n1->category, 'blarf', "attr correct";
ok !$n1->_prev->category, "previous version attr still empty";
my $prev = $n1->_prev;
ok $n1->set_model('test2'), "change another attr (shouldn't dup)";
is $n1->_prev, $prev, "didn't dup";
is $prev->_next, $n1, "yep";

# how about the owner, r1
is $r1->_prev->src, $n1->_prev, "old r1 points to old n1";

#ok $model->put, 'put';
$DB::single=1;
1;

#         r1       r21 --
#       /   \    /        \
#    n1*      n2 --       n31
#            /|\    \      /
#          p1 p2 p3 p41  p21

is $model->version_count(4), 4, "bump version count";

my ($p41);

# why does adding a new property to node generate dups of all of the
# previously attached properties??

ok $p41 = $P->new({handle=>'p41'}), 'make p41';
$DB::single =1;
ok $model->add_prop($n2 => $p41), "add p41 to n2 (generates dup)";
ok $n2->_prev, "yep";
$DB::single=1;
is $r1->dst, $n2, "current r1 points to current n2";
is $r1->_prev->dst, $n2->_prev, "old r1 points to old n2 still";
ok !$n2->_prev->props('p41'), "p41 not on prev n2";
is $n2->props('p41'),$p41, "on current";

ok $model->put,'put';
$DB::single=1;
1;

# match (e) where (e._from <= $V) and (($V < e._to) or (not exists(e._to))) return e;
# :param V => 1

diag "Access versions";

$DB::single=1;
ok my $v1 = $model->at_version(1), "v1";
ok my $v2 = $model->at_version(2), "v2";
ok my $v3 = $model->at_version(3), "v3";
ok my $v4 = $model->at_version(4), "v4";



done_testing;

END {
  $docker->stop;
  $docker->rm;
}
