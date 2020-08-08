from pysb import *

model = Model()

A = Monomer('A', ['s1'], {'s1': ['u', 'l']})
B = Monomer('B', ['s1'], {'s1': ['u', 'l']})
k = Parameter('k', 0.1)
# r1 = Rule('r1', A() @ {'s1': 'a'} >> B() @ {'s1': 'a'}, k)
r1 = Rule('r1', A(s1=StateReference('a')) >> B(s1=StateReference('a')), k)

a0 = Parameter('a0', 1)
Initial(A({'s1':'l'}), a0)
Initial(A({'s1':'u'}), a0)



t = [0, 10, 20, 30, 40, 50, 60]
from pysb.integrate import Solver
solver = Solver(model, t)
solver.run()
print(model.species)
print(solver.y)
