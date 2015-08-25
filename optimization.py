from pulp import *
prob = LpProblem("Knapsack problem", LpMaximize)
W = [8, 40, 30]
P = [5377, 17923, 13439]
X = [LpVariable('x{}'.format(i), 0, 1, 'Integer') for i in range(1, 4)]
prob += sum([x*p for x, p in zip(X, P)]), 'obj'
prob += sum([x*w for x, w in zip(X, W)]) <= 42, 'c1'
prob.solve()
for v in prob.variables():
    print v.name, '=', v.varValue
print ("objective = %s$" % value(prob.objective))