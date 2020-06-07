use Test::More;
use Test::Exception;
use Test::Warn;
use lib '../lib';
use Bento::Meta::Model;
use strict;

our $B = 'Bento::Meta::Model';
our $N = "${B}::Node";
our $E = "${B}::Edge";
our $V = "${B}::ValueSet";
our $T = "${B}::Term";
our $P = "${B}::Property";

my $model = Bento::Meta::Model->new('test');
ok !$model->versioning(), "not versioning yet";
ok $model->versioning(1), "set versioning";
ok $model->versioning, "yes is set";
dies_ok { $N->new({handle => 'case', model => 'test', tags => ['florp', 'blerg']}) } "new: versioning on, but version count not defined";
like $@, qr/not currently defined/;
is $model->version_count(3), 3, "set count to 3";
is $model->version_count, 3, "yes is set";

$model->version_count(1);

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
ok $n2->set_props(p1 => $p1);
ok $n2->set_props(p2 => $p2);
ok $n2->set_props(p3 => $p3);

is $r1->src, $n1;
is $r1->dst, $n2;
is $n2->props('p1'), $p1;
  
for my $e ($n1,$n2,$r1,$p1,$p2,$p3) {
  is $e->_from, 1, 'from set (1)';
  ok !$e->_to, 'to unset';
}

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
ok $n21->set_props('p21' => $p21);

is $r1->dst, $r21->src, 'same object';

for my $e ($r21,$n21,$p21) {
  is $e->_from, 2, 'from set (2)';
  ok !$e->_to, 'to unset';
}
for my $e ($n1,$n2,$r1,$p1,$p2,$p3) {
  is $e->_from, 1, 'v1 nodes still v1';
}

#         r1       r21 ------
#       /   \    /            \
#    n1*      n2      XXn21XX  n31
#            /|\              /
#          p1 p2 p3    p21---

is $model->version_count(3), 3, "bump version count";

my ($n31);

ok $n31 = $N->new({handle => 'n31'});
ok $n21->del, "del n21";

ok $r21->set_dst($n31), "connect to n31 (generates dup)";

is $r21->dst, $n31, "connected";
ok $r21->_prev, "prev version n31 exists";
is $r21->_prev->_next, $r21, "two-way link";
is $r21->_prev->handle, 'r21', "prev version called r21";
is $r21->_prev->dst, $n21, "prev version still linked to n21";

$DB::single=1;
ok $n1->set_category('blarf'), "set a scalar attribute (generates dup)";
is $n1->category, 'blarf', "attr correct";
ok !$n1->_prev->category, "previous version attr still empty";
ok ref($n1->_prev->_prev) eq 'SCALAR', 'only two versions of n1';
ok $r1->_prev, "changing n1 induced a change on r1 (n1 owner)";
is $r1->src->category, 'blarf', "latest r1 src, i.e., n1, has category attr.";
ok !$r1->_prev->src->category, "but old r1 src, i.e., old n1, has no category attr.";
ok ref($r1->_prev->_prev) eq 'SCALAR', 'only two versions of r1';
my $prev = $n1->_prev;
ok $n1->set_model('test2'), "change another attr (shouldn't dup)";
is $n1->_prev, $prev, "didn't dup";
is $prev->_next, $n1, "yep";

#         r1       r21 --
#       /   \    /        \
#    n1*      n2 --       n31
#            /|\    \      /
#          p1 p2 p3 p41  p21

is $model->version_count(4), 4, "bump version count";

my ($p41);

ok $p41 = $P->new({handle=>'p41'});
ok $n2->set_props('p41' => $p41), "add p41 to n2 (generates dup)";
ok $n2->_prev, "yep";
ok !$n2->_prev->props('p41'), "p41 not on prev n2";
is $n2->props('p41'),$p41, "on current";


done_testing;
