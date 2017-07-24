"""
Module containing a class to return the StochKit XML equivalent of a model

Contains code based on the `gillespy <https://github.com/JohnAbel/gillespy>`
library with permission from author Brian Drawert.

For information on how to use the model exporters, see the documentation
for :py:mod:`pysb.export`.
"""
from pysb.export import Exporter
from pysb.core import as_complex_pattern
from pysb.bng import generate_equations
import numpy as np
import sympy
import re
try:
    import lxml.etree as etree
    pretty_print = True
except ImportError:
    import xml.etree.ElementTree as etree
    import xml.dom.minidom
    pretty_print = False


class StochKitExporter(Exporter):
    """A class for returning the Kappa for a given PySB model.

    Inherits from :py:class:`pysb.export.Exporter`, which implements
    basic functionality for all exporters.
    """
    @staticmethod
    def _species_to_element(species_num, species_val):
        e = etree.Element('Species')
        idElement = etree.Element('Id')
        idElement.text = species_num
        e.append(idElement)

        initialPopulationElement = etree.Element('InitialPopulation')
        initialPopulationElement.text = str(species_val)
        e.append(initialPopulationElement)

        return e


    @staticmethod
    def _parameter_to_element(param_name, param_val):
        e = etree.Element('Parameter')
        idElement = etree.Element('Id')
        idElement.text = param_name
        e.append(idElement)
        expressionElement = etree.Element('Expression')
        expressionElement.text = str(param_val)
        e.append(expressionElement)
        return e


    @staticmethod
    def _reaction_to_element(rxn_name, rxn_desc, propensity_fxn, reactants,
                             products):
        e = etree.Element('Reaction')

        idElement = etree.Element('Id')
        idElement.text = rxn_name
        e.append(idElement)

        descriptionElement = etree.Element('Description')
        descriptionElement.text = rxn_desc
        e.append(descriptionElement)

        typeElement = etree.Element('Type')
        typeElement.text = 'customized'
        e.append(typeElement)
        functionElement = etree.Element('PropensityFunction')
        functionElement.text = propensity_fxn
        e.append(functionElement)

        reactantElement = etree.Element('Reactants')

        for reactant, stoichiometry in reactants.items():
            srElement = etree.Element('SpeciesReference')
            srElement.set('id', reactant)
            srElement.set('stoichiometry', str(stoichiometry))
            reactantElement.append(srElement)

        e.append(reactantElement)

        productElement = etree.Element('Products')
        for product, stoichiometry in products.items():
            srElement = etree.Element('SpeciesReference')
            srElement.set('id', product)
            srElement.set('stoichiometry', str(stoichiometry))
            productElement.append(srElement)
        e.append(productElement)

        return e

    def export(self, initials=None, param_values=None):
        """Generate the corresponding StochKit2 XML for a PySB model

        Parameters
        ----------
        initials : list of numbers
            List of initial species concentrations overrides
            (must be same length as model.species). If None,
            the concentrations from the model are used.
        param_values : list
            List of parameter value overrides (must be same length as
            model.parameters). If None, the parameter values from the model
            are used.

        Returns
        -------
        string
            The model in StochKit2 XML format
        """
        generate_equations(self.model)
        document = etree.Element("Model")

        d = etree.Element('Description')

        d.text = 'Exported from PySB Model: %s' % self.model.name
        document.append(d)

        # Number of Reactions
        nr = etree.Element('NumberOfReactions')
        nr.text = str(len(self.model.reactions))
        document.append(nr)

        # Number of Species
        ns = etree.Element('NumberOfSpecies')
        ns.text = str(len(self.model.species))
        document.append(ns)

        if param_values is None:
            # Get parameter values from model if not supplied
            param_values = [p.value for p in self.model.parameters]
        else:
            # Validate length
            if len(param_values) != len(self.model.parameters):
                raise Exception('param_values must be a list of numeric '
                                'parameter values the same length as '
                                'model.parameters')

        # Get initial species concentrations from model if not supplied
        if initials is None:
            initials = np.zeros((len(self.model.species),))
            subs = dict((p, param_values[i]) for i, p in
                        enumerate(self.model.parameters))

            for cp, value_obj in self.model.initial_conditions:
                cp = as_complex_pattern(cp)
                si = self.model.get_species_index(cp)
                if si is None:
                    raise IndexError("Species not found in model: %s" %
                                     repr(cp))
                if isinstance(value_obj, (int, float)):
                    value = value_obj
                elif value_obj in self.model.parameters:
                    pi = self.model.parameters.index(value_obj)
                    value = param_values[pi]
                elif value_obj in self.model.expressions:
                    value = value_obj.expand_expr().evalf(subs=subs)
                else:
                    raise ValueError(
                        "Unexpected initial condition value type")
                initials[si] = value
        else:
            # Validate length
            if len(initials) != len(self.model.species):
                raise Exception('initials must be a list of numeric initial '
                                'concentrations the same length as '
                                'model.species')

        # Species
        spec = etree.Element('SpeciesList')
        for s_id in range(len(self.model.species)):
            spec.append(self._species_to_element('__s%d' % s_id,
                                                 initials[s_id]))
        document.append(spec)

        # Parameters
        params = etree.Element('ParametersList')
        for p_id, param in enumerate(self.model.parameters):
            p_value = param.value if param_values is None else \
                param_values[p_id]
            params.append(self._parameter_to_element(param.name, p_value))
        # Default volume parameter value
        params.append(self._parameter_to_element('vol', 1.0))

        document.append(params)

        # Reactions
        reacs = etree.Element('ReactionsList')
        for rxn_id, rxn in enumerate(self.model.reactions):
            rxn_name = 'Rxn%d' % rxn_id
            rxn_desc = 'Rules: %s' % rxn["rule"]

            reactants = {}
            products = {}
            # reactants
            for r in rxn["reactants"]:
                r = "__s%d" % r
                if r in reactants:
                    reactants[r] += 1
                else:
                    reactants[r] = 1
            # products
            for p in rxn["products"]:
                p = "__s%d" % p
                if p in products:
                    products[p] += 1
                else:
                    products[p] = 1
            # replace terms like __s**2 with __s*(__s-1)
            rate = str(rxn["rate"])
            pattern = "(__s\d+)\*\*(\d+)"
            matches = re.findall(pattern, rate)
            for m in matches:
                repl = m[0]
                for i in range(1, int(m[1])):
                    repl += "*(%s-%d)" % (m[0], i)
                rate = re.sub(pattern, repl, rate)
            # expand expressions
            for e in self.model.expressions:
                rate = re.sub(r'\b%s\b' % e.name,
                              '(%s)' % sympy.ccode(e.expand_expr(self.model)),
                              rate)
            # replace observables w/ sums of species
            for obs in self.model.observables:
                obs_string = ''
                for i in range(len(obs.coefficients)):
                    if i > 0:
                        obs_string += "+"
                    if obs.coefficients[i] > 1:
                        obs_string += str(obs.coefficients[i]) + "*"
                    obs_string += "__s" + str(obs.species[i])
                if len(obs.coefficients) > 1:
                    obs_string = '(' + obs_string + ')'
                rate = re.sub(r'%s' % obs.name, obs_string, rate)

            reacs.append(self._reaction_to_element(rxn_name,
                                                   rxn_desc,
                                                   rate,
                                                   reactants,
                                                   products))
        document.append(reacs)

        if pretty_print:
            return etree.tostring(document, pretty_print=True)
        else:
            # Hack to print pretty xml without pretty-print
            # (requires the lxml module).
            doc = etree.tostring(document)
            xmldoc = xml.dom.minidom.parseString(doc)
            uglyXml = xmldoc.toprettyxml(indent='  ')
            text_re = re.compile(">\n\s+([^<>\s].*?)\n\s+</", re.DOTALL)
            prettyXml = text_re.sub(">\g<1></", uglyXml)
            return prettyXml