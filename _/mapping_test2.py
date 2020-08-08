from pysb import *
model = Model()

Monomer('A', ['c1', 'c2', 'c3'],
        {'c1': ['u', 'l'], 'c2': ['u', 'l'], 'c3': ['u', 'l']})
Monomer('B', ['c1', 'c2', 'c3'],
        {'c1': ['u', 'l'], 'c2': ['u', 'l'], 'c3': ['u', 'l']})
Monomer('C', ['c1', 'c2'], {'c1': ['u', 'l'], 'c2': ['u', 'l']})
Monomer('D', ['c1', 'c2', 'c3'],
        {'c1': ['u', 'l'], 'c2': ['u', 'l'], 'c3': ['u', 'l']})
Monomer('E', ['c1'], {'c1': ['u', 'l']})
Monomer('F', ['c1', 'c2', 'c3'],
        {'c1': ['u', 'l'], 'c2': ['u', 'l'], 'c3': ['u', 'l']})

Parameter('r1_k', 1.0)
Parameter('r2_k', 1.0)
Parameter('r3_k', 1.0)
Parameter('r4_k', 1.0)
Parameter('r5_k', 1.0)
Parameter('r6_k', 1.0)
Parameter('A_l_ini', 100.0)

Compartment(name='extracellular', parent=None, dimension=3, size=None)
Initial(A(c1='u', c2='l', c3='l') ** extracellular, A_l_ini)


# need parentheses because right-associative
Rule('r1_0', (A() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular >> (B(c1='u', c2='u', c3='u') @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular, r1_k)
Rule('r2_0', (B() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular | (D() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular,
     r2_k, r3_k)
Rule('r6_0', (D() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular >> (F() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'})** extracellular,
     r6_k)

# wrong in other model?
Rule('r4_0', (B() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular >> (C() @ {'c1': 'b', 'c2': 'c'}) ** extracellular + (E() @ {'c1': 'a'}) ** extracellular, r4_k)
Rule('r5_0', (B() @ {'c1': 'a', 'c2': 'b', 'c3': 'c'}) ** extracellular + (C() @ {'c1': 'd', 'c2': 'e'}) ** extracellular >> (D() @ {'c1': 'b', 'c2': 'c', 'c3': 'd'}) ** extracellular + (E() @ {'c1': 'a'}) ** extracellular + (E() @ {'c1': 'e'}) ** extracellular, r5_k)

t = [0, 10, 20, 30, 40, 50, 60]
from pysb.integrate import Solver
from pysb.bng import generate_equations
#generate_equations(model)
solver = Solver(model, t)
solver.run()
import pandas as pd
pd.set_option('max_colwidth', 100)
pd.set_option('max_columns', 100)
pd.set_option('expand_frame_repr', False)
print(pd.DataFrame({k: v for k, v in zip(model.species, solver.y)}))
