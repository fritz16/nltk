# Natural Language Toolkit: Combinatory Categorial Grammar
#
# Copyright (C) 2001-2015 NLTK Project
# Author: Graeme Gange <ggange@csse.unimelb.edu.au>
# URL: <http://nltk.org/>
# For license information, see LICENSE.TXT
"""
CCG Lexicons
"""

from __future__ import unicode_literals

import re
from collections import defaultdict

from nltk.ccg.api import PrimitiveCategory, Direction, CCGVar, FunctionalCategory
from nltk.compat import python_2_unicode_compatible

#------------
# Regular expressions used for parsing components of the lexicon
#------------

# Parses a primitive category and subscripts
PRIM_RE = re.compile(r'''([A-Za-z]+)(\[[A-Za-z,]+\])?''')

# Separates the next primitive category from the remainder of the
# string
NEXTPRIM_RE = re.compile(r'''([A-Za-z]+(?:\[[A-Za-z,]+\])?)(.*)''')

# Separates the next application operator from the remainder
APP_RE = re.compile(r'''([\\/])([.,]?)([.,]?)(.*)''')

# Parses the definition of the category of either a word or a family
LEX_RE = re.compile(r'''([\w_]+)\s*(::|[-=]+>)\s*(.+)''', re.UNICODE)

# Strips comments from a line
COMMENTS_RE = re.compile('''([^#]*)(?:#.*)?''')

#----------
# Lexicons
#----------

@python_2_unicode_compatible
class CCGLexicon(object):
    """
    Class representing a lexicon for CCG grammars.
    
    * `primitives`: The list of primitive categories for the lexicon
    * `families`: Families of categories
    * `entries`: A mapping of words to possible categories
    """
    def __init__(self, start, primitives, families, entries):
        self._start = PrimitiveCategory(start)
        self._primitives = primitives
        self._families = families
        self._entries = entries

    
    def categories(self, word):
        """
        Returns all the possible categories for a word
        """
        return self._entries[word]


    def start(self):
        """
        Return the target category for the parser
        """
        return self._start

    def __str__(self):
        """
        String representation of the lexicon. Used for debugging.
        """
        string = ""
        first = True
        for ident in self._entries:
            if not first:
                string = string + "\n"
            string = string + ident + " => "

            first = True
            for cat in self._entries[ident]:
                if not first:
                    string = string + " | "
                else:
                    first = False
                string = string + "%s" % cat
        return string


#-----------
# Parsing lexicons
#-----------


def matchBrackets(string):
    """
    Separate the contents matching the first set of brackets from the rest of
    the input.
    """
    rest = string[1:]
    inside = "("

    while rest != "" and not rest.startswith(')'):
        if rest.startswith('('):
            (part, rest) = matchBrackets(rest)
            inside = inside + part
        else:
            inside = inside + rest[0]
            rest = rest[1:]
    if rest.startswith(')'):
        return (inside + ')', rest[1:])
    raise AssertionError('Unmatched bracket in string \'' + string + '\'')


def nextCategory(string):
    """
    Separate the string for the next portion of the category from the rest
    of the string
    """
    if string.startswith('('):
        return matchBrackets(string)
    return NEXTPRIM_RE.match(string).groups()

def parseApplication(app):
    """
    Parse an application operator
    """
    return Direction(app[0], app[1:])


def parseSubscripts(subscr):
    """
    Parse the subscripts for a primitive category
    """
    if subscr:
        return subscr[1:-1].split(',')
    return []


def parsePrimitiveCategory(chunks, primitives, families, var):    
    """
    Parse a primitive category
    
    If the primitive is the special category 'var', replace it with the
    correct `CCGVar`.
    """
    if chunks[0] == "var":
        if chunks[1] is None:
            if var is None:
                var = CCGVar()
            return (var, var)

    catstr = chunks[0]
    if catstr in families:
        (cat, cvar) = families[catstr]
        if var is None:
            var = cvar
        else:
            cat = cat.substitute([(cvar, var)])
        return (cat, var)

    if catstr in primitives:
        subscrs = parseSubscripts(chunks[1])
        return (PrimitiveCategory(catstr, subscrs), var)
    raise AssertionError('String \'' + catstr + '\' is neither a family nor primitive category.')


def parseCategory(line, primitives, families):
    """
    Drop the 'var' from the tuple
    """
    return augParseCategory(line, primitives, families)[0]


def augParseCategory(line, primitives, families, var=None):
    """
    Parse a string representing a category, and returns a tuple with
    (possibly) the CCG variable for the category
    """
    (cat_string, rest) = nextCategory(line)

    if cat_string.startswith('('):
        (res, var) = augParseCategory(cat_string[1:-1], primitives, families, var)

    else:
#        print rePrim.match(str).groups()
        (res, var) =\
            parsePrimitiveCategory(PRIM_RE.match(cat_string).groups(), primitives,
                                   families, var)

    while rest != "":
        app = APP_RE.match(rest).groups()
        direction = parseApplication(app[0:3])
        rest = app[3]

        (cat_string, rest) = nextCategory(rest)
        if cat_string.startswith('('):
            (arg, var) = augParseCategory(cat_string[1:-1], primitives, families, var)
        else:
            (arg, var) =\
                parsePrimitiveCategory(PRIM_RE.match(cat_string).groups(),
                                       primitives, families, var)
        res = FunctionalCategory(res, arg, direction)

    return (res, var)


def fromstring(lex_str):
    """
    Convert string representation into a lexicon for CCGs.
    """
    primitives = []
    families = {}
    entries = defaultdict(list)
    for line in lex_str.splitlines():
        # Strip comments and leading/trailing whitespace.
        line = COMMENTS_RE.match(line).groups()[0].strip()
        if line == "":
            continue

        if line.startswith(':-'):
            # A line of primitive categories.
            # The first one is the target category
            # ie, :- S, N, NP, VP
            primitives = primitives + [prim.strip() for prim in line[2:].strip().split(',')]
        else:
            # Either a family definition, or a word definition
            (ident, sep, catstr) = LEX_RE.match(line).groups()
            (cat, var) = augParseCategory(catstr, primitives, families)
            if sep == '::':
                # Family definition
                # ie, Det :: NP/N
                families[ident] = (cat, var)
            else:
                # Word definition
                # ie, which => (N\N)/(S/NP)
                entries[ident].append(cat)
    return CCGLexicon(primitives[0], primitives, families, entries)


openccg_tinytiny = fromstring("""
    # Rather minimal lexicon based on the openccg `tinytiny' grammar.
    # Only incorporates a subset of the morphological subcategories, however.
    :- S,NP,N                    # Primitive categories
    Det :: NP/N                  # Determiners
    Pro :: NP
    IntransVsg :: S\\NP[sg]    # Tensed intransitive verbs (singular)
    IntransVpl :: S\\NP[pl]    # Plural
    TransVsg :: S\\NP[sg]/NP   # Tensed transitive verbs (singular)
    TransVpl :: S\\NP[pl]/NP   # Plural

    the => NP[sg]/N[sg]
    the => NP[pl]/N[pl]

    I => Pro
    me => Pro
    we => Pro
    us => Pro

    book => N[sg]
    books => N[pl]

    peach => N[sg]
    peaches => N[pl]

    policeman => N[sg]
    policemen => N[pl]

    boy => N[sg]
    boys => N[pl]

    sleep => IntransVsg
    sleep => IntransVpl

    eat => IntransVpl
    eat => TransVpl
    eats => IntransVsg
    eats => TransVsg

    see => TransVpl
    sees => TransVsg
    """)
