use Test::More;
use Test::Exception;
use Test::Warn;
use lib '../lib';
use strict;

use_ok('Bento::Meta::Model');

our $B = 'Bento::Meta::Model';
our $N = "${B}::Node";
our $E = "${B}::Edge";
our $P = "${B}::Property";

ok my $model = $B->new('test'), 'create model';
isa_ok($model, $B);
dies_ok {$B->new()} 'new reqs $handle';
is $model->handle, 'test', 'model handle set';

ok my $case = $N->new({
  handle => 'case',
  model => 'test',
  tags => ['florp', 'blerg']
 }), 'create Node';
isa_ok($case, $N);
isa_ok($case, "${B}::Entity");
is $case->handle, 'case', 'attr1';
is $case->model, 'test', 'attr2';
is_deeply [$case->tags],[qw/florp blerg/], 'attr3';

ok my $ret = $model->add_node($case), 'add Node obj';
is $ret, $case, 'add_node returns the Node';

ok $ret = $model->add_node({ handle => 'sample'}), 'add node with init hash';
is $ret->model, 'test', 'add_node sets model attr';
is scalar $model->nodes, 2, 'two nodes';

ok my $case_id = $P->new({ handle => 'case_id', value_domain => 'string' }), 'create Property';
isa_ok($case_id, $P);
  
ok $ret = $model->add_prop($case, $case_id), 'added Property to Node';
is $ret, $case_id, 'add_prop returns the Property';
ok $ret = $model->add_prop($case, {handle=>'patient_id',value_domain=>'string'}), 'add prop with init hash';
is $ret->model, $model->handle, 'add_props sets model attr';
is $ret->value_domain,'string', 'prop attr correct';
is $case->props('patient_id'), $ret, 'retrieve prop from Node obj';
is $model->prop('case:patient_id'), $ret, 'retrieve prop from Model obj';

ok $case = $model->node('case'), "get case node";
ok my $sample = $model->node('sample'), "get sample node";
ok my $of_case = $E->new({handle => 'of_case',
                          src => $sample,
                          dst => $case}), 'create Edge obj';
isa_ok($of_case,$E);
isa_ok($of_case->src, $N);
isa_ok($of_case->dst, $N);
is $of_case->triplet, 'of_case:sample:case', 'edge triplet string';

ok my $ret = $model->add_edge($of_case), 'add Edge object';
is $ret, $of_case, 'add_edge returns Edge';
is $model->edge('of_case',$sample,$case), $of_case, 'retrieve edge by components';
is $model->edge('of_case','sample','case'), $of_case, 'retrieve edge by handles';
is $model->edge('of_case:sample:case'), $of_case, 'retrieve edge by triplet';

ok $ret = $model->add_edge({handle => 'has_sample',
                            src => $case,
                            dst => $sample}), "add edge with init hash";
is $ret->triplet,'has_sample:case:sample', 'correct triplet string';

ok $ret = $model->add_prop($of_case, { handle => 'consent_on', value_domain => 'datetime' }), 'add prop to edge';

is $ret->handle, 'consent_on', 'prop handle set';
is $of_case->props('consent_on'), $ret, 'retrieve prop from Edge obj';
is $model->prop('of_case:sample:case:consent_on'), $ret, 'retrieve prop from Model obj';

done_testing;

