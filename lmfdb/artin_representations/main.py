# -*- coding: utf-8 -*-
# This Blueprint is about Artin representations
# Author: Paul-Olivier Dehaye, John Jones

import re, random

from flask import render_template, request, url_for, redirect
from sage.all import ZZ

from lmfdb import db
from lmfdb.utils import (
    parse_primes, parse_restricted, parse_element_of, parse_galgrp,
    parse_ints, parse_container, parse_bool, clean_input, flash_error,
    SearchArray, TextBox, TextBoxNoEg, ParityBox, CountBox, SubsetNoExcludeBox, TextBoxWithSelect,
    display_knowl, search_wrap, to_dict)
from lmfdb.artin_representations import artin_representations_page
#from lmfdb.artin_representations import artin_logger
from lmfdb.artin_representations.math_classes import (
    ArtinRepresentation, num2letters)


LABEL_RE = re.compile(r'^\d+\.\d+\.\d+(t\d+)?\.[a-z]+\.[a-z]+$')
ORBIT_RE = re.compile(r'^\d+\.\d+\.\d+(t\d+)?\.[a-z]+$')
OLD_LABEL_RE = re.compile(r'^\d+\.\d+(e\d+)?(_\d+(e\d+)?)*\.\d+(t\d+)?\.\d+c\d+$')
OLD_ORBIT_RE = re.compile(r'^\d+\.\d+(e\d+)?(_\d+(e\d+)?)*\.\d+(t\d+)?\.\d+$')


# Utility for permutations
def cycle_string(lis):
    from sage.combinat.permutation import Permutation
    return Permutation(lis).cycle_string()

def get_bread(breads=[]):
    bc = [("Artin Representations", url_for(".index"))]
    for b in breads:
        bc.append(b)
    return bc

def learnmore_list():
    return [('Completeness of the data', url_for(".cande")),
            ('Source of the data', url_for(".source")),
            ('Reliability of the data', url_for(".reliability")),
            ('Artin representations labels', url_for(".labels_page"))]

# Return the learnmore list with the matchstring entry removed
def learnmore_list_remove(matchstring):
    return [t for t in learnmore_list() if t[0].find(matchstring) < 0]


def make_cond_key(D):
    D1 = ZZ(D)
    if D1 < 1:
        D1 = ZZ.one()
    D1 = int(D1.log(10))
    return '%04d%s' % (D1, str(D))


def parse_artin_orbit_label(label, safe=False):
    try:
        label = clean_input(label)
        if ORBIT_RE.match(label):
            return label
        if OLD_ORBIT_RE.match(label):
            newlabel = db.artin_old2new_labels.lookup(label)['new']
            if newlabel:
                return newlabel
    except:
        if safe:
            return ''
    raise ValueError

def parse_artin_label(label, safe=False):
    try:
        label = clean_input(label)
        if LABEL_RE.match(label):
            return label
        if OLD_LABEL_RE.match(label):
            newlabel = db.artin_old2new_labels.lookup(label)['new']
        if newlabel:
            return newlabel
    except:
        if safe:
            return ''
    raise ValueError

def both_labels(label):
    both = db.artin_old2new_labels.lucky({'$or': [{'old':label}, {'new': label}]})
    if both:
        return list(both.values())
    else:
        return [label]

# Is it a rep'n or an orbit, supporting old and new styles
def parse_any(label):
    try:
        newlabel = parse_artin_label(label)
        return ['rep', newlabel]
    except:
        try:
            newlabel = parse_artin_orbit_label(label)
            return ['orbit', newlabel]
        except:
            return ['malformed', label]


def add_lfunction_friends(friends, label):
    for label in both_labels(label):
        rec = db.lfunc_instances.lucky({'type':'Artin','url':'ArtinRepresentation/'+label})
        if rec:
            num = 10 if 'c' in label.split('.')[-1] else 8 # number of components of CMF lable based on artin label (rep or orbit)
            for r in db.lfunc_instances.search({'Lhash':rec["Lhash"]}):
                s = r['url'].split('/')
                if r['type'] == 'CMF' and len(s) == num:
                    cmf_label = '.'.join(s[4:])
                    url = r['url'] if r['url'][0] == '/' else '/' + r['url']
                    friends.append(("Modular form " + cmf_label, url))
    return friends

@artin_representations_page.route("/")
def index():
    info = to_dict(request.args, search_array=ArtinSearchArray())
    bread = get_bread()
    if not request.args:
        return render_template("artin-representation-index.html", title="Artin Representations", bread=bread, learnmore=learnmore_list(), info=info)
    else:
        return artin_representation_search(info)

def artin_representation_jump(info):
    label = info['jump']
    try:
        label = parse_artin_label(label)
    except ValueError:
        try:
            label = parse_artin_orbit_label(label)
        except ValueError:
            flash_error("%s is not in a valid form for an Artin representation label", label)
            return redirect(url_for(".index"))
    return redirect(url_for(".render_artin_representation_webpage", label=label), 307)

@search_wrap(template="artin-representation-search.html",
             table=db.artin_reps,
             title='Artin Representation Search Results',
             err_title='Artin Representation Search Error',
             per_page=50,
             learnmore=learnmore_list,
             url_for_label=lambda label: url_for(".render_artin_representation_webpage", label=label),
             shortcuts={'jump':artin_representation_jump},
             bread=lambda:[('Artin Representations', url_for(".index")), ('Search Results', ' ')],
             initfunc=lambda:ArtinRepresentation)
def artin_representation_search(info, query):
    query['Hide'] = 0
    info['sign_code'] = 0
    parse_primes(info,query,"unramified",name="Unramified primes",
                 qfield="BadPrimes",mode="exclude")
    parse_primes(info,query,"ramified",name="Ramified primes",
                 qfield="BadPrimes",mode=info.get("ram_quantifier"))
    parse_element_of(info,query,"root_number",qfield="GalConjSigns")
    parse_restricted(info,query,"frobenius_schur_indicator",qfield="Indicator",
                     allowed=[1,0,-1],process=int)
    parse_container(info,query, 'container',qfield='Container', name="Smallest permutation representation")
    parse_galgrp(info,query,"group",name="Group",qfield=("GaloisLabel",None))
    parse_ints(info,query,'dimension',qfield='Dim')
    parse_ints(info,query,'conductor',qfield='Conductor')
    # Backward support for old URLs
    if 'Is_Even' in info:
        info['parity'] = info.pop('Is_Even')
    parse_bool(info,query,'parity',qfield='Is_Even')

def search_input_error(info, bread):
    return render_template("artin-representation-search.html", req=info, title='Artin Representation Search Error', bread=bread)

@artin_representations_page.route("/<dim>/<conductor>/")
def by_partial_data(dim, conductor):
    return artin_representation_search({'dimension': dim, 'conductor': conductor, 'search_array': ArtinSearchArray()})


# credit information should be moved to the databases themselves, not at the display level. that's too late.
tim_credit = "Tim Dokchitser, John Jones, and David Roberts"
support_credit = "Support by Paul-Olivier Dehaye."

@artin_representations_page.route("/<label>/")
@artin_representations_page.route("/<label>")
def render_artin_representation_webpage(label):
    if re.compile(r'^\d+$').match(label):
        return artin_representation_search(**{'dimension': label, 'search_array': ArtinSearchArray()})

    # label=dim.cond.nTt.indexcj, c is literal, j is index in conj class
    # Should we have a big try around this to catch bad labels?
    clean_label = clean_input(label)
    if clean_label != label:
        return redirect(url_for('.render_artin_representation_webpage', label=clean_label), 301)
    # We could have a single representation or a Galois orbit
    case = parse_any(label)
    if case[0] == 'malformed':
        try:
            raise ValueError
        except:
            flash_error("%s is not in a valid form for the label for an Artin representation or a Galois orbit of Artin representations", label)
            return redirect(url_for(".index"))
    # Do this twice to customize error messages
    newlabel = case[1]
    case = case[0]
    if case == 'rep':
        try:
            the_rep = ArtinRepresentation(newlabel)
        except:
            newlabel = parse_artin_label(label)
            flash_error("Artin representation %s is not in database", label)
            return redirect(url_for(".index"))
    else: # it is an orbit
        try:
            the_rep = ArtinRepresentation(newlabel+'.a')
        except:
            newlabel = parse_artin_orbit_label(newlabel)
            flash_error("Galois orbit of Artin representations %s is not in database", label)
            return redirect(url_for(".index"))
        # in this case we want all characters
        num_conj = the_rep.galois_conjugacy_size()
        allchars = [ ArtinRepresentation(newlabel+'.'+num2letters(j)).character_formatted() for j in range(1,num_conj+1)]

    label = newlabel
    bread = get_bread([(label, ' ')])

    #artin_logger.info("Found %s" % (the_rep._data))

    if case=='rep':
        title = "Artin representation %s" % label
    else:
        title = "Galois orbit of Artin representations %s" % label
    the_nf = the_rep.number_field_galois_group()
    if the_rep.sign() == 0:
        processed_root_number = "not computed"
    else:
        processed_root_number = str(the_rep.sign())
    properties = [("Label", label),
                  ("Dimension", str(the_rep.dimension())),
                  ("Group", the_rep.group()),
                  ("Conductor", "$" + the_rep.factored_conductor_latex() + "$")]
    if case == 'rep':
        properties.append( ("Root number", processed_root_number) )
    properties.append( ("Frobenius-Schur indicator", str(the_rep.indicator())) )

    friends = []
    nf_url = the_nf.url_for()
    if nf_url:
        friends.append(("Artin Field", nf_url))
    if case == 'rep':
        cc = the_rep.central_character()
        if cc is not None:
            if the_rep.dimension()==1:
                if cc.order == 2:
                    cc_name = cc.symbol
                else:
                    cc_name = cc.texname
                friends.append(("Dirichlet character "+cc_name, url_for("characters.render_Dirichletwebpage", modulus=cc.modulus, number=cc.number)))
            else:
                detrep = the_rep.central_character_as_artin_rep()
                friends.append(("Determinant representation "+detrep.label(), detrep.url_for()))
        add_lfunction_friends(friends,label)

        # once the L-functions are in the database, the link can always be shown
        #if the_rep.dimension() <= 6:
        if the_rep.dimension() == 1:
            # Zeta is loaded differently
            if cc.modulus == 1 and cc.number == 1:
                friends.append(("L-function", url_for("l_functions.l_function_dirichlet_page", modulus=cc.modulus, number=cc.number)))
            else:
                # looking for Lhash dirichlet_L_modulus.number
                mylhash = 'dirichlet_L_%d.%d'%(cc.modulus,cc.number)
                lres = db.lfunc_instances.lucky({'Lhash': mylhash})
                if lres is not None:
                    friends.append(("L-function", url_for("l_functions.l_function_dirichlet_page", modulus=cc.modulus, number=cc.number)))

        # Dimension > 1
        elif int(the_rep.conductor())**the_rep.dimension() <= 729000000000000:
            friends.append(("L-function", url_for("l_functions.l_function_artin_page",
                                              label=the_rep.label())))
        orblabel = re.sub(r'\.[a-z]+$', '', label)
        friends.append(("Galois orbit "+orblabel,
            url_for(".render_artin_representation_webpage", label=orblabel)))
    else:
        add_lfunction_friends(friends,label)
        friends.append(("L-function", url_for("l_functions.l_function_artin_page", label=the_rep.label())))
        for j in range(1,1+the_rep.galois_conjugacy_size()):
            newlabel = label+'.'+num2letters(j)
            friends.append(("Artin representation "+newlabel,
                url_for(".render_artin_representation_webpage", label=newlabel)))

    info={} # for testing

    if case == 'rep':
        return render_template("artin-representation-show.html", credit=tim_credit, support=support_credit, title=title, bread=bread, friends=friends, object=the_rep, cycle_string=cycle_string, properties=properties, info=info, learnmore=learnmore_list())
    # else we have an orbit
    return render_template("artin-representation-galois-orbit.html", credit=tim_credit, support=support_credit, title=title, bread=bread, allchars=allchars, friends=friends, object=the_rep, cycle_string=cycle_string, properties=properties, info=info, learnmore=learnmore_list())

@artin_representations_page.route("/random")
def random_representation():
    rep = db.artin_reps.random(projection=2)
    num = random.randrange(len(rep['GaloisConjugates']))
    label = rep['Baselabel']+"."+num2letters(num+1)
    return redirect(url_for(".render_artin_representation_webpage", label=label), 307)

@artin_representations_page.route("/Labels")
def labels_page():
    t = 'Labels for Artin Representations'
    bread = get_bread([("Labels", '')])
    learnmore = learnmore_list_remove('labels')
    return render_template("single.html", kid='artin.label',learnmore=learnmore, credit=tim_credit, title=t, bread=bread)

@artin_representations_page.route("/Source")
def source():
    t = 'Source of Artin Representation Data'
    bread = get_bread([("Source", '')])
    learnmore = learnmore_list_remove('Source')
    return render_template("single.html", kid='rcs.source.artin',
                           credit=tim_credit, title=t, bread=bread, 
                           learnmore=learnmore)

@artin_representations_page.route("/Reliability")
def reliability():
    t = 'Reliability of Artin Representation Data'
    bread = get_bread([("Reliability", '')])
    learnmore = learnmore_list_remove('Reliability')
    return render_template("single.html", kid='rcs.rigor.artin',
                           credit=tim_credit, title=t, bread=bread, 
                           learnmore=learnmore)

@artin_representations_page.route("/Completeness")
def cande():
    t = 'Completeness of Artin Representation Data'
    bread = get_bread([("Completeness", '')])
    learnmore = learnmore_list_remove('Completeness')
    return render_template("single.html", kid='rcs.cande.artin',
                           credit=tim_credit, title=t, bread=bread, 
                           learnmore=learnmore)

class ArtinSearchArray(SearchArray):
    noun = "representation"
    plural_noun = "representations"
    jump_example = "4.5648.6t13.b.a"
    jump_egspan = "e.g. 4.5648.6t13.b.a"
    def __init__(self):
        dimension = TextBox(
            name="dimension",
            label="Dimension",
            knowl="artin.dimension",
            example="2",
            example_span="1, 2-4")
        conductor = TextBox(
            name="conductor",
            label="Conductor",
            knowl="artin.conductor",
            example="51,100-200")
        group = TextBoxNoEg(
            name="group",
            label="Group",
            knowl="artin.gg_quotient",
            example="A5",
            example_span="list of %s, e.g. [8,3] or [16,7], group names from the %s, e.g. C5 or S12, and %s, e.g., 7T2 or 11T5" % (
                display_knowl("group.small_group_label", "GAP id's"),
                display_knowl("nf.galois_group.name", "list of group labels"),
                display_knowl("gg.label", "transitive group labels")))
        parity = ParityBox(
            name="parity",
            label="Parity",
            knowl="artin.parity")
        container = TextBox(
            name="container",
            label="Smallest permutation container",
            knowl="artin.permutation_container",
            example="6T13",
            example_span="6T13 or 7T6")
        ram_quantifier = SubsetNoExcludeBox(
            name="ram_quantifier")
        ramified = TextBoxWithSelect(
            name="ramified",
            label="Ramified primes",
            knowl="artin.ramified_primes",
            example="2, 3",
            select_box=ram_quantifier,
            example_span="2, 3 (no range allowed)")
        unramified = TextBox(
            name="unramified",
            label="Unramified primes",
            knowl="artin.unramified_primes",
            example="5,7",
            example_span="5, 7, 13 (no range allowed)")
        root_number = TextBoxNoEg(
            name="root_number",
            label="Root number",
            knowl="artin.root_number",
            example="1",
            example_span="at the moment, one of 1 or -1")
        fsind = TextBoxNoEg(
            name="frobenius_schur_indicator",
            label="Frobenius-Schur indicator",
            knowl="artin.frobenius_schur_indicator",
            example="1",
            example_span="+1 for orthogonal, -1 for symplectic, 0 for non-real character")
        count = CountBox()

        self.browse_array = [
            [dimension],
            [conductor],
            [group],
            [parity],
            [container],
            [ramified],
            [unramified],
            [root_number],
            [fsind],
            [count]]

        self.refine_array = [
            [dimension, conductor, group, root_number, parity],
            [container, ramified, unramified, fsind]]
