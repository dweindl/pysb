from pysb import *

model = Model()

A = Monomer('A', ['s1', 's2'], {'s1': ['u', 'l'], 's2': ['u', 'l']})
B = Monomer('B', ['s1', 's2'], {'s1': ['u', 'l'], 's2': ['u', 'l']})
k = Parameter('k', 0.1)
# r1 = Rule('r1', A() @ {'s1': 'a'} >> B() @ {'s1': 'a'}, k)
e1 = Expression('e1', 0.5*k)
r1 = Rule('r1', A(s1=StateReference('a'), s2=StateReference('b'))
          >> B(s1=StateReference('a'), s2=StateReference('b')), e1)
r2 = Rule('r2',  A(s1=StateReference('a'), s2=StateReference('b'))
          >> B(s1=StateReference('b'), s2=StateReference('a')), e1)


a0 = Parameter('a0', 1)
Initial(A({'s1':'l', 's2': 'u'}), a0)
#Initial(A({'s1':'u'}), a0)



t = [0, 10, 20, 30, 40, 50, 60]
from pysb.integrate import Solver
solver = Solver(model, t)
solver.run()
print(model.species)
print(solver.y)
