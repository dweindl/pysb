import pysb.core
from pysb.generator.bng import BngGenerator
import os
import subprocess
import random
import re
import itertools
import sympy
import numpy
from StringIO import StringIO


# Cached value of BNG path
_bng_path = None

def set_bng_path(dir):
    global _bng_path
    _bng_path = os.path.join(dir,'BNG2.pl')
    # Make sure file exists and that it is not a directory
    if not os.access(_bng_path, os.F_OK) or not os.path.isfile(_bng_path):
        raise Exception('Could not find BNG2.pl in ' + os.path.abspath(dir) + '.')
    # Make sure file has executable permissions
    elif not os.access(_bng_path, os.X_OK):
        raise Exception("BNG2.pl in " + os.path.abspath(dir) + " does not have executable permissions.")

def _get_bng_path():
    """
    Return the path to BioNetGen's BNG2.pl.

    Looks for a BNG distribution at the path stored in the BNGPATH environment
    variable if that's set, or else in a few hard-coded standard locations.

    """

    global _bng_path

    # Just return cached value if it's available
    if _bng_path:
        return _bng_path

    path_var = 'BNGPATH'
    dist_dirs = [
        '/usr/local/share/BioNetGen',
        'c:/Program Files/BioNetGen',
        ]
    # BNG 2.1.8 moved BNG2.pl up out of the Perl2 subdirectory, so to be more
    # compatible we check both the old and new locations.
    script_subdirs = ['', 'Perl2']

    def check_dist_dir(dist_dir):
        # Return the full path to BNG2.pl inside a BioNetGen distribution
        # directory, or False if directory does not contain a BNG2.pl in one of
        # the expected places.
        for subdir in script_subdirs:
            script_path = os.path.join(dist_dir, subdir, 'BNG2.pl')
            if os.access(script_path, os.F_OK):
                return script_path
        else:
            return False

    # First check the environment variable, which has the highest precedence
    if path_var in os.environ:
        script_path = check_dist_dir(os.environ[path_var])
        if not script_path:
            raise Exception('Environment variable %s is set but BNG2.pl could'
                            ' not be found there' % path_var)
    # If the environment variable isn't set, check the standard locations
    else:
        for dist_dir in dist_dirs:
            script_path = check_dist_dir(dist_dir)
            if script_path:
                break
        else:
            raise Exception('Could not find BioNetGen installed in one of the '
                            'following locations:' +
                            ''.join('\n    ' + d for d in dist_dirs))
    # Cache path for future use
    _bng_path = script_path
    return script_path

class GenerateNetworkError(RuntimeError):
    """BNG reported an error when trying to generate a network for a model."""
    pass

_generate_network_code = """
begin actions
generate_network({overwrite=>1});
end actions
"""


def _parse_bng_outfile(out_filename):
    """
    Load and return data from a BNG .gdat or .cdat output file.

    The format of the output files is an initial line of the form::

        #   time   obs1    obs2    obs3  ...

    The column headers are separated by a differing number of spaces (not tabs).
    This function parses out the column names and then uses the numpy.loadtxt
    method to load the outputfile into a numpy record array.

    Parameters
    ----------
    out_filename : string
        Path of file to load.

    """

    try:
        out_file = open(out_filename, 'r')

        line = out_file.readline().strip() # Get the first line
        out_file.close()
        line = line[2:]  # strip off opening '# '
        raw_names = re.split('\s*', line)
        column_names = [raw_name for raw_name in raw_names if not raw_name == '']

        # Create the dtype argument for the numpy record array
        dt = zip(column_names, ('float',)*len(column_names))

        # Load the output file as a numpy record array, skip the name row
        arr = numpy.loadtxt(out_filename, dtype=dt, skiprows=1)
    
    except Exception as e:
        # FIXME special Exception/Error?
        raise Exception("problem parsing BNG outfile: " + str(e)) 
    
    return arr


def run_ssa(model, t_end=10, n_steps=100, output_dir='/tmp', cleanup=True, verbose=False, **additional_args):
    """
    Simulate a model with BNG's SSA simulator and return the trajectories.

    Parameters
    ----------
    model : Model
        Model to simulate.
    t_end : number, optional
        Final time point of the simulation.
    n_steps : int, optional
        Number of steps in the simulation.
    output_dir : string, optional
        Location for temporary files generated by BNG. Defaults to '/tmp'.
    cleanup : bool, optional
        If True (default), delete the temporary files after the simulation is
        finished. If False, leave them in place (in `output_dir`). Useful for
        debugging.
    verbose: bool, optional
        If True, print BNG screen output.
    additional_args: kwargs, optional
        Additional arguments to pass to BioNetGen

    """
    
    ssa_args = "t_end=>%f, n_steps=>%d" % (t_end, n_steps)
    for key,val in additional_args.items(): ssa_args += ", "+key+"=>"+str(val)
    if verbose: ssa_args += ", verbose=>1"
        
    run_ssa_code = """
    begin actions
    generate_network({overwrite=>1})
    simulate_ssa({%s})
    end actions
    """ % (ssa_args)
    
    gen = BngGenerator(model)
    bng_filename = '%s_%d_%d_temp.bngl' % (model.name,
                            os.getpid(), random.randint(0, 10000))
    gdat_filename = bng_filename.replace('.bngl', '.gdat')
    cdat_filename = bng_filename.replace('.bngl', '.cdat')
    net_filename = bng_filename.replace('.bngl', '.net')

    output = StringIO()

    try:
        working_dir = os.getcwd()
        os.chdir(output_dir)
        bng_file = open(bng_filename, 'w')
        bng_file.write(gen.get_content())
        bng_file.write(run_ssa_code)
        bng_file.close()
        p = subprocess.Popen(['perl', _get_bng_path(), bng_filename],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if verbose:
            for line in iter(p.stdout.readline, b''):
                print line,
        (p_out, p_err) = p.communicate()
        if p.returncode:
            raise GenerateNetworkError(p_out.rstrip("at line")+"\n"+p_err.rstrip())

        output_arr = _parse_bng_outfile(gdat_filename)
        #ssa_file = open(ssa_filename, 'r')
        #output.write(ssa_file.read())
        #net_file.close()
        #if append_stdout:
        #    output.write("#\n# BioNetGen execution log follows\n# ==========")
        #    output.write(re.sub(r'(^|\n)', r'\n# ', p_out))
    finally:
        if cleanup:
            for filename in [bng_filename, gdat_filename,
                             cdat_filename, net_filename]:
                if os.access(filename, os.F_OK):
                    os.unlink(filename)
        os.chdir(working_dir)
    return output_arr

def generate_network(model, cleanup=True, append_stdout=False, verbose=False):
    """
    Return the output from BNG's generate_network function given a model.

    The output is a BNGL model definition with additional sections 'reactions'
    and 'groups', and the 'species' section expanded to contain all possible
    species. BNG refers to this as a 'net' file.

    Parameters
    ----------
    model : Model
        Model to pass to generate_network.
    cleanup : bool, optional
        If True (default), delete the temporary files after the simulation is
        finished. If False, leave them in place (in `output_dir`). Useful for
        debugging.
    append_stdout : bool, optional
        If True, provide BNG2.pl's standard output stream as comment lines
        appended to the net file contents. If False (default), do not append it.

    """
    gen = BngGenerator(model)
    if not model.initial_conditions:
        raise NoInitialConditionsError()
    if not model.rules:
        raise NoRulesError()
    bng_filename = '%s_%d_%d_temp.bngl' % (model.name, os.getpid(), random.randint(0, 10000))
    net_filename = bng_filename.replace('.bngl', '.net')
    output = StringIO()
    try:
        bng_file = open(bng_filename, 'w')
        bng_file.write(gen.get_content())
        bng_file.write(_generate_network_code)
        bng_file.close()
        p = subprocess.Popen(['perl', _get_bng_path(), bng_filename],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if verbose:
            for line in iter(p.stdout.readline, b''):
                print line,
        (p_out, p_err) = p.communicate()
        if p.returncode:
            raise GenerateNetworkError(p_out.rstrip()+"\n"+p_err.rstrip())
        ######
#         p = subprocess.call(['perl', _get_bng_path(), bng_filename])
#         if p:
#             raise GenerateNetworkError(p_out.rstrip()+"\n"+p_err.rstrip())
        ######
        net_file = open(net_filename, 'r')
        output.write(net_file.read())
        net_file.close()
        if append_stdout:
            output.write("#\n# BioNetGen execution log follows\n# ==========")
            output.write(re.sub(r'(^|\n)', r'\n# ', p_out))
    finally:
        if cleanup:
            for filename in [bng_filename, net_filename]:
                if os.access(filename, os.F_OK):
                    os.unlink(filename)
    return output.getvalue()


def generate_equations(model, verbose=False):
    """
    Generate math expressions for reaction rates and species in a model.

    This fills in the following pieces of the model:

    * odes
    * species
    * reactions
    * reactions_bidirectional
    * observables (just `coefficients` and `species` fields for each element)

    """
    # only need to do this once
    # TODO track "dirty" state, i.e. "has model been modified?"
    #   or, use a separate "math model" object to contain ODEs
    if model.odes:
        return
    lines = iter(generate_network(model,verbose=verbose).split('\n'))
    try:
        while 'begin species' not in lines.next():
            pass
        model.species = []
        while True:
            line = lines.next()
            if 'end species' in line: break
            _parse_species(model, line)

        while 'begin reactions' not in lines.next():
            pass
        model.odes = [sympy.numbers.Zero()] * len(model.species)
        reaction_cache = {}
        while True:
            line = lines.next()
            if 'end reactions' in line: break
            (number, reactants, products, rate, rule) = line.strip().split()
            # the -1 is to switch from one-based to zero-based indexing
            reactants = tuple(int(r) - 1 for r in reactants.split(','))
            products = tuple(int(p) - 1 for p in products.split(','))
            rate = rate.rsplit('*')
            (rule_name, is_reverse) = re.match(r'#(\w+)(?:\((reverse)\))?', rule).groups()
            is_reverse = bool(is_reverse)
#             r_names = ['s%d' % r for r in reactants]
            r_names = ['__s%d' % r for r in reactants]
            combined_rate = sympy.Mul(*[sympy.Symbol(t) for t in r_names + rate])
            rule = model.rules[rule_name]
            reaction = {
                'reactants': reactants,
                'products': products,
                'rate': combined_rate,
                'rule': rule_name,
                'reverse': is_reverse,
                }
            model.reactions.append(reaction)
            key = (rule_name, reactants, products)
            key_reverse = (rule_name, products, reactants)
            reaction_bd = reaction_cache.get(key_reverse)
            if reaction_bd is None:
                # make a copy of the reaction dict
                reaction_bd = dict(reaction)
                # default to false until we find a matching reverse reaction
                reaction_bd['reversible'] = False
                reaction_cache[key] = reaction_bd
                model.reactions_bidirectional.append(reaction_bd)
            else:
                reaction_bd['reversible'] = True
                reaction_bd['rate'] -= combined_rate
            for p in products:
                model.odes[p] += combined_rate
            for r in reactants:
                model.odes[r] -= combined_rate
        # fix up reactions whose reverse version we saw first
        for r in model.reactions_bidirectional:
            if r['reverse']:
                r['reactants'], r['products'] = r['products'], r['reactants']
                r['rate'] *= -1
            # now the 'reverse' value is no longer needed
            del r['reverse']

        while 'begin groups' not in lines.next():
            pass
        while True:
            line = lines.next()
            if 'end groups' in line: break
            _parse_group(model, line)

    except StopIteration as e:
        pass


def _parse_species(model, line):
    """Parse a 'species' line from a BNGL net file."""
    index, species, value = line.strip().split()
    complex_compartment_name, complex_string = re.match(r'(?:@(\w+)::)?(.*)', species).groups()
    monomer_strings = complex_string.split('.')
    monomer_patterns = []
    for ms in monomer_strings:
        monomer_name, site_strings, monomer_compartment_name = re.match(r'(\w+)\(([^)]*)\)(?:@(\w+))?', ms).groups()
        site_conditions = {}
        if len(site_strings):
            for ss in site_strings.split(','):
                # FIXME this should probably be done with regular expressions
                if '!' in ss and '~' in ss:
                    site_name, condition = ss.split('~')
                    state, bond = condition.split('!')
                    if bond == '?':
                        bond = pysb.core.WILD
                    elif bond == '!':
                        bond = pysb.core.ANY
                    else:
                        bond = int(bond)
                    condition = (state, bond)
                elif '!' in ss:
                    site_name, condition = ss.split('!', 1)
                    if '!' in condition:
                        condition = [int(c) for c in condition.split('!')]
                    else:
                        condition = int(condition)
                elif '~' in ss:
                    site_name, condition = ss.split('~')
                else:
                    site_name, condition = ss, None
                site_conditions[site_name] = condition
        monomer = model.monomers[monomer_name]
        monomer_compartment = model.compartments.get(monomer_compartment_name)
        mp = pysb.core.MonomerPattern(monomer, site_conditions, monomer_compartment)
        monomer_patterns.append(mp)

    complex_compartment = model.compartments.get(complex_compartment_name)
    cp = pysb.core.ComplexPattern(monomer_patterns, complex_compartment)
    model.species.append(cp)


def _parse_group(model, line):
    """Parse a 'group' line from a BNGL net file."""
    # values are number (which we ignore), name, and species list
    values = line.strip().split()
    obs = model.observables[values[1]]
    if len(values) == 3:
        # combination is a comma separated list of [coeff*]speciesnumber
        for product in values[2].split(','):
            terms = product.split('*')
            # if no coeff given (just species), insert a coeff of 1
            if len(terms) == 1:
                terms.insert(0, 1)
            obs.coefficients.append(int(terms[0]))
            # -1 to change to 0-based indexing
            obs.species.append(int(terms[1]) - 1)


class NoInitialConditionsError(RuntimeError):
    """Model initial_conditions is empty."""
    def __init__(self):
        RuntimeError.__init__(self, "Model has no initial conditions")

class NoRulesError(RuntimeError):
    """Model rules is empty."""
    def __init__(self):
        RuntimeError.__init__(self, "Model has no rules")
