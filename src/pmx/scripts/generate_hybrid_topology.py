#!/usr/bin/env python
# pmx  Copyright Notice
# ============================
#
# The pmx source code is copyrighted, but you can freely use and
# copy it as long as you don't change or remove any of the copyright
# notices.
#
# ----------------------------------------------------------------------
# pmx is Copyright (C) 2006-2013 by Daniel Seeliger
#
#                        All Rights Reserved
#
# Permission to use, copy, modify, distribute, and distribute modified
# versions of this software and its documentation for any purpose and
# without fee is hereby granted, provided that the above copyright
# notice appear in all copies and that both the copyright notice and
# this permission notice appear in supporting documentation, and that
# the name of Daniel Seeliger not be used in advertising or publicity
# pertaining to distribution of the software without specific, written
# prior permission.
#
# DANIEL SEELIGER DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS
# SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS.  IN NO EVENT SHALL DANIEL SEELIGER BE LIABLE FOR ANY
# SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
# ----------------------------------------------------------------------

import sys
import os
import argparse
from copy import deepcopy
from pmx.model import Model
from pmx.forcefield import Topology
from pmx.mutdb import read_mtp_entry
from pmx.utils import mtpError, get_ff_path, ff_selection
from pmx.utils import get_mtp_file
from pmx.library import _perturbed_nucleotides


def check_case(atoms):
    A = ''
    B = ''
    for a in atoms:
        if a.atomtype.startswith('DUM'):
            A += 'D'
        else:
            A += 'A'
        if a.atomtypeB is not None:
            if a.atomtypeB.startswith('DUM'):
                B += 'D'
            else:
                B += 'A'
        else:
            B += 'A'
    return A, B


def dump_atoms_and_exit(msg, atoms):
    print >>sys.stderr, 'err_> ', msg
    print >>sys.stderr, 'err_>  name      resname      atomtype       atomtypeB       bondtype       bondtypeB'
    for atom in atoms:
        print >>sys.stderr, atom.name, atom.resname, atom.atomtype, atom.atomtypeB, atom.type, atom.typeB
    print >>sys.stderr, 'err_> Exiting'
    sys.exit(1)


def atoms_morphe(atoms):
    for atom in atoms:
        if atom.atomtypeB is not None and (atom.q != atom.qB or atom.m != atom.mB or atom.atomtype != atom.atomtypeB):
            return True
    return False


def types_morphe(atoms):
    for atom in atoms:
        if atom.atomtypeB is not None and atom.atomtype != atom.atomtypeB:
            return True
    return False


def proline_dihedral_decouplings(topol, rlist, rdic):
    for r in rlist:
        if 'P' in r.resname:
            # identify in which state proline sits
            prolineState = 'A'
            if '2P' in r.resname:
                prolineState = 'B'

            # find the atoms for which the bond needs to be broken
            prolineCDatom = ''
            prolineCBatom = ''
            prolineNatom = ''
            prolineCAatom = ''
            for a in r.atoms:
                if (prolineState == 'A') and (a.name == 'CD'):
                    prolineCDatom = a
                elif (prolineState == 'A') and (a.name == 'N'):
                    prolineNatom = a
                elif (prolineState == 'A') and (a.name == 'CB'):
                    prolineCBatom = a
                elif (prolineState == 'A') and (a.name == 'CA'):
                    prolineCAatom = a
                elif (prolineState == 'B') and (a.name == 'DCD'):
                    prolineCDatom = a
                elif (prolineState == 'B') and (a.name == 'N'):
                    prolineNatom = a
                elif (prolineState == 'B') and (a.name == 'DCB'):
                    prolineCBatom = a
                elif (prolineState == 'B') and (a.name == 'CA'):
                    prolineCAatom = a

            # decouple [CD and N] dihedrals
            for dih in topol.dihedrals:
                a1 = dih[0]
                a2 = dih[1]
                a3 = dih[2]
                a4 = dih[3]
                func = dih[4]
                if ((a1.id == prolineCDatom.id and a2.id == prolineNatom.id)) or \
                   ((a2.id == prolineCDatom.id and a1.id == prolineNatom.id)) or \
                   ((a1.id == prolineCDatom.id and a3.id == prolineNatom.id)) or \
                   ((a3.id == prolineCDatom.id and a1.id == prolineNatom.id)) or \
                   ((a1.id == prolineCDatom.id and a4.id == prolineNatom.id)) or \
                   ((a4.id == prolineCDatom.id and a1.id == prolineNatom.id)) or \
                   ((a2.id == prolineCDatom.id and a3.id == prolineNatom.id)) or \
                   ((a3.id == prolineCDatom.id and a2.id == prolineNatom.id)) or \
                   ((a2.id == prolineCDatom.id and a4.id == prolineNatom.id)) or \
                   ((a4.id == prolineCDatom.id and a2.id == prolineNatom.id)) or \
                   ((a3.id == prolineCDatom.id and a4.id == prolineNatom.id)) or \
                   ((a4.id == prolineCDatom.id and a3.id == prolineNatom.id)):
                    if (dih[5] == 'NULL') or (dih[6] == 'NULL'):
                        continue
                    if prolineState == 'A':
                        if func == 3:
                            dih[6] = [func, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        elif func == 2:
                            dih[6] = [func, dih[6][1], 0.0]
                        else:
                            dih[6] = [func, dih[6][1], 0.0, dih[6][-1]]
                    if prolineState == 'B':
                        if func == 3:
                            dih[5] = [func, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        elif func == 2:
                            dih[5] = [func, dih[6][1], 0.0]
                        else:
                            dih[5] = [func, dih[6][1], 0.0, dih[6][-1]]

            # decouple [CB and CA] dihedrals
            for dih in topol.dihedrals:
                a1 = dih[0]
                a2 = dih[1]
                a3 = dih[2]
                a4 = dih[3]
                func = dih[4]
                if ((a1.id == prolineCBatom.id and a2.id == prolineCAatom.id)) or \
                   ((a2.id == prolineCBatom.id and a1.id == prolineCAatom.id)) or \
                   ((a1.id == prolineCBatom.id and a3.id == prolineCAatom.id)) or \
                   ((a3.id == prolineCBatom.id and a1.id == prolineCAatom.id)) or \
                   ((a1.id == prolineCBatom.id and a4.id == prolineCAatom.id)) or \
                   ((a4.id == prolineCBatom.id and a1.id == prolineCAatom.id)) or \
                   ((a2.id == prolineCBatom.id and a3.id == prolineCAatom.id)) or \
                   ((a3.id == prolineCBatom.id and a2.id == prolineCAatom.id)) or \
                   ((a2.id == prolineCBatom.id and a4.id == prolineCAatom.id)) or \
                   ((a4.id == prolineCBatom.id and a2.id == prolineCAatom.id)) or \
                   ((a3.id == prolineCBatom.id and a4.id == prolineCAatom.id)) or \
                   ((a4.id == prolineCBatom.id and a3.id == prolineCAatom.id)):
                    if (dih[5] == 'NULL') or (dih[6] == 'NULL'):
                        continue
                    if prolineState == 'A':
                        if func == 3:
                            dih[6] = [func, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        elif func == 2:
                            dih[6] = [func, dih[6][1], 0.0]
                        else:
                            dih[6] = [func, dih[6][1], 0.0, dih[6][-1]]
                    if prolineState == 'B':
                        if func == 3:
                            dih[5] = [func, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        elif func == 2:
                            dih[5] = [func, dih[6][1], 0.0]
                        else:
                            dih[5] = [func, dih[6][1], 0.0, dih[6][-1]]


def proline_decouplings(topol, rlist, rdic):
    for r in rlist:
        if 'P' in r.resname:
            # identify in which state proline sits
            prolineState = 'A'
            if '2P' in r.resname:
                prolineState = 'B'

            # find the atoms for which the bond needs to be broken
            prolineCDatom = ''
            prolineCGatom = ''
            for a in r.atoms:
                if (prolineState == 'A') and (a.name == 'CD'):
                    prolineCDatom = a
                elif (prolineState == 'A') and (a.name == 'CG'):
                    prolineCGatom = a
                elif (prolineState == 'B') and (a.name == 'DCD'):
                    prolineCDatom = a
                elif (prolineState == 'B') and (a.name == 'DCG'):
                    prolineCGatom = a

            # break the bond
            for b in topol.bonds:
                a1 = b[0]
                a2 = b[1]
                if ((a1.id == prolineCDatom.id) and (a2.id == prolineCGatom.id)) or \
                   ((a2.id == prolineCDatom.id) and (a1.id == prolineCGatom.id)):
                    if prolineState == 'A':
                        b[4] = deepcopy(b[3])
                        b[4][2] = 0.0
                    elif prolineState == 'B':
                        b[3] = deepcopy(b[4])
                        b[3][2] = 0.0

            # decouple angles
            for ang in topol.angles:
                a1 = ang[0]
                a2 = ang[1]
                a3 = ang[2]
                func = ang[3]
                if ((a1.id == prolineCDatom.id and a2.id == prolineCGatom.id)) or \
                   ((a2.id == prolineCDatom.id and a1.id == prolineCGatom.id)) or \
                   ((a1.id == prolineCDatom.id and a3.id == prolineCGatom.id)) or \
                   ((a3.id == prolineCDatom.id and a1.id == prolineCGatom.id)) or \
                   ((a2.id == prolineCDatom.id and a3.id == prolineCGatom.id)) or \
                   ((a3.id == prolineCDatom.id and a2.id == prolineCGatom.id)):
                    if prolineState == 'A':
                        if func == 5:
                            ang[5] = [1, 0, 0, 0, 0]
                        else:
                            ang[5] = [1, 0, 0]
                    elif prolineState == 'B':
                        if func == 5:
                            ang[4] = [1, 0, 0, 0, 0]
                        else:
                            ang[4] = [1, 0, 0]

            # decouple dihedrals
            for dih in topol.dihedrals:
                a1 = dih[0]
                a2 = dih[1]
                a3 = dih[2]
                a4 = dih[3]
                func = dih[4]
                if ((a1.id == prolineCDatom.id and a2.id == prolineCGatom.id)) or \
                   ((a2.id == prolineCDatom.id and a1.id == prolineCGatom.id)) or \
                   ((a1.id == prolineCDatom.id and a3.id == prolineCGatom.id)) or \
                   ((a3.id == prolineCDatom.id and a1.id == prolineCGatom.id)) or \
                   ((a1.id == prolineCDatom.id and a4.id == prolineCGatom.id)) or \
                   ((a4.id == prolineCDatom.id and a1.id == prolineCGatom.id)) or \
                   ((a2.id == prolineCDatom.id and a3.id == prolineCGatom.id)) or \
                   ((a3.id == prolineCDatom.id and a2.id == prolineCGatom.id)) or \
                   ((a2.id == prolineCDatom.id and a4.id == prolineCGatom.id)) or \
                   ((a4.id == prolineCDatom.id and a2.id == prolineCGatom.id)) or \
                   ((a3.id == prolineCDatom.id and a4.id == prolineCGatom.id)) or \
                   ((a4.id == prolineCDatom.id and a3.id == prolineCGatom.id)):
                    if (dih[5] == 'NULL') or (dih[6] == 'NULL'):
                        continue

                    if prolineState == 'A':
                        if func == 3:
                            dih[6] = [func, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        elif func == 2:
                            dih[6] = [func, dih[6][1], 0.0]
                        else:
                            dih[6] = [func, dih[6][1], 0.0, dih[6][-1]]
                    if prolineState == 'B':
                        if func == 3:
                            dih[5] = [func, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                        elif func == 2:
                            dih[5] = [func, dih[6][1], 0.0]
                        else:
                            dih[5] = [func, dih[6][1], 0.0, dih[6][-1]]


def find_bonded_entries(topol):
    count = 0
    for b in topol.bonds:
        a1, a2, func = b
        A, B = check_case([a1, a2])
        if a1.atomtypeB is not None or a2.atomtypeB is not None:
            count += 1
            error_occured = False
            astate = None
            bstate = None
            if A == 'AA' and B == 'AA':  # we need A and B state
                astate = topol.BondedParams.get_bond_param(a1.type, a2.type)
                bstate = topol.BondedParams.get_bond_param(a1.typeB, a2.typeB)
                b.extend([astate, bstate])
            elif 'D' in A and B == 'AA':
                bstate = topol.BondedParams.get_bond_param(a1.typeB, a2.typeB)
                astate = bstate
                b.extend([astate, bstate])
            elif 'D' in B and A == 'AA':
                astate = topol.BondedParams.get_bond_param(a1.type, a2.type)
                bstate = astate
                b.extend([astate, bstate])
            # catch errors
            elif 'D' in B and 'D' in A:
                print('Error: fake bond '
                      '%s-%s (%s-%s -> %s-%s)' % (a1.name, a2.name,
                                                  a1.atomtype, a2.atomtype,
                                                  a1.atomtypeB, a2.atomtypeB))
                sys.exit(1)
            if astate is None:
                print('Error A: No bond entry found for astate '
                      '%s-%s (%s-%s -> %s-%s)' % (a1.name, a2.name,
                                                  a1.atomtype, a2.atomtype,
                                                  a1.type, a2.type))
                print 'Resi = %s' % a1.resname
                error_occured = True

            if bstate is None:
                print('Error B: No bond entry found for bstate '
                      '%s-%s (%s-%s -> %s-%s)' % (a1.name, a2.name,
                                                  a1.atomtypeB, a2.atomtypeB,
                                                  a1.typeB, a2.typeB))
                error_occured = True
            if error_occured:
                sys.exit(1)
    print('log_> Making bonds for state B -> %d bonds with perturbed atoms'
          % count)


def find_angle_entries(topol):
    count = 0
    for a in topol.angles:
        a1, a2, a3, func = a
        astate = None
        bstate = None
        if a1.atomtypeB is not None or \
           a2.atomtypeB is not None or \
           a3.atomtypeB is not None:
            A, B = check_case([a1, a2, a3])
            count += 1
            if 'D' in A and 'D' in B:  # fake angle
                if func == 5:
                    astate = [1, 0, 0, 0, 0]
                    bstate = [1, 0, 0, 0, 0]
                else:
                    astate = [1, 0, 0]
                    bstate = [1, 0, 0]
                a.extend([astate, bstate])
            elif A == 'AAA' and 'D' in B:   # take astate
                astate = topol.BondedParams.get_angle_param(a1.type,
                                                            a2.type,
                                                            a3.type)
                bstate = astate
                a.extend([astate, bstate])
            elif 'D' in A and B == 'AAA':   # take bstate
                bstate = topol.BondedParams.get_angle_param(a1.typeB,
                                                            a2.typeB,
                                                            a3.typeB)
                astate = bstate
                a.extend([astate, bstate])
            elif A == 'AAA' and B == 'AAA':
                if a1.atomtypeB != a1.atomtype or \
                   a2.atomtypeB != a2.atomtype or \
                   a3.atomtypeB != a3.atomtype:
                    astate = topol.BondedParams.get_angle_param(a1.type,
                                                                a2.type,
                                                                a3.type)
                    bstate = topol.BondedParams.get_angle_param(a1.typeB,
                                                                a2.typeB,
                                                                a3.typeB)
                    a.extend([astate, bstate])
                else:
                    astate = topol.BondedParams.get_angle_param(a1.type,
                                                                a2.type,
                                                                a3.type)
                    bstate = astate
                    a.extend([astate, bstate])
            if astate is None:
                dump_atoms_and_exit("No angle entry (state A)", [a1, a2, a3])
            if bstate is None:
                dump_atoms_and_exit("No angle entry (state B)", [a1, a2, a3])

    print('log_> Making angles for state B -> %d angles with perturbed atoms'
          % count)


def check_dih_ILDN_OPLS(topol, rlist, rdic, a1, a2, a3, a4):
    counter = 0
    for r in rlist:
        if r.id == a2.resnr:
            dih = rdic[r.resname][3]
            for d in dih:
                if counter == 1:
                    break
                al = []
                for name in d[:4]:
                    atom = r.fetch(name)[0]
                    al.append(atom)

                if (a1.id == al[0].id and a2.id == al[1].id and
                   a3.id == al[2].id and a4.id == al[3].id) or \
                   (a1.id == al[3].id and a2.id == al[2].id and
                   a3.id == al[1].id and a4.id == al[0].id):
                    # ---------------
                    # checks for OPLS
                    # ---------------
                    if d[4].startswith('dih_') and d[5].startswith('dih_'):
                        counter = 42
                        break
                    elif d[4].startswith('dih_') and 'un' in d[5]:
                        counter = 2
                        break
                    elif 'un' in d[4] and d[5].startswith('dih_'):
                        counter = 3
                        break
                    # ---------------
                    # checks for ILDN
                    # ---------------
                    if d[4].startswith('torsion') and d[5].startswith('torsion'):
                        counter = 42
                        break
                    elif d[4].startswith('torsion') and 'un' in d[5]:
                        counter = 2
                        break
                    elif 'un' in d[4] and d[5].startswith('torsion'):
                        counter = 3
                        break
                    elif 'un' in d[4]:
                        counter = 1
                        break
    return counter


def is_dih_undef(visited_dih, d):
    encountered = 0
    undef = 0
    for dih in visited_dih:
        if (dih[0].id == d[0].id and dih[1].id == d[1].id
           and dih[2].id == d[2].id and dih[3].id == d[3].id):
            if (dih[-1] == 'undefA'):
                undef = 1
                break
            elif (dih[-1] == 'undefB'):
                undef = 2
                break
            elif (dih[-1] == 'undefA_ildn'):
                undef = 3
                break
            elif (dih[-1] == 'undefB_ildn'):
                undef = 4
                break
            else:
                encountered = 1
                break

    return (undef, encountered)


def is_dih_encountered_strict(visited_dih, d, encountered):
    for dih in visited_dih:
        if (dih[0].id == d[0].id and dih[1].id == d[1].id
           and dih[2].id == d[2].id and dih[3].id == d[3].id):
            encountered = 1
            break
    return encountered


def find_dihedral_entries(topol, rlist, rdic, dih_predef_default):
    count = 0
    nfake = 0
    # here I will accumulate multiple entries of type 9 dihedrals
    dih9 = []
    # need to store already visited angles to avoid multiple re-definitions
    visited_dih = []

    for d in topol.dihedrals:
        if len(d) >= 6:
            # only consider the dihedral, if it has not been encountered so far
            undef = 0
            encountered = 0

            undef, encountered = is_dih_undef(dih_predef_default, d)
            encountered = is_dih_encountered_strict(visited_dih, d,
                                                    encountered)
            if(encountered == 1):
                continue

            visited_dih.append(d)

            if undef == 3 or undef == 4:
                a1 = d[0]
                a2 = d[1]
                a3 = d[2]
                a4 = d[3]
                val = ''
                func = 9
            elif(len(d) == 6):
                a1, a2, a3, a4, func, val = d
            else:
                a1, a2, a3, a4, func, val, rest = d

            backup_d = d[:6]

            if atoms_morphe([a1, a2, a3, a4]):
                A, B = check_case(d[:4])
                if A != 'AAAA' and B != 'AAAA':
                    nfake += 1
                    # these are fake dihedrals
                    d[5] = 'NULL'
                    d.append('NULL')
                else:
                    count += 1
                    astate = []
                    bstate = []
                    if A == 'AAAA' and B != 'AAAA':
                        foo = topol.BondedParams.get_dihedral_param(a1.type,
                                                                    a2.type,
                                                                    a3.type,
                                                                    a4.type,
                                                                    func)
                        # need to check if the dihedral has torsion pre-defined
                        counter = check_dih_ILDN_OPLS(topol, rlist, rdic,
                                                      a1, a2, a3, a4)
                        if counter == 42:
                            continue

                        for ast in foo:
                            if counter == 0:
                                d[5] = ast
                                d.append(ast)
                            else:
                                alus = backup_d[:]
                                alus[5] = ast
                                alus.append(ast)
                                dih9.append(alus)
                            counter = 1

                    elif B == 'AAAA' and A != 'AAAA':
                        foo = topol.BondedParams.get_dihedral_param(a1.typeB,
                                                                    a2.typeB,
                                                                    a3.typeB,
                                                                    a4.typeB,
                                                                    func)
                        # need to check if the dihedral has torsion pre-defined
                        counter = check_dih_ILDN_OPLS(topol,rlist,rdic, a1, a2, a3, a4)

                        if counter == 42:
                            continue

                        for bst in foo:
                            if counter == 0:
                                d[5] = bst
                                d.append(bst)
                            else:
                                alus = backup_d[:]
                                alus[5] = bst
                                alus.append(bst)
                                dih9.append(alus)
                            counter = 1

                    elif A == 'AAAA' and B == 'AAAA':
                        # disappear/appear dihedrals, do not morphe
                        if val == '':
                            if(undef != 4):
                                astate = topol.BondedParams.get_dihedral_param(a1.type,
                                                                               a2.type,
                                                                               a3.type,
                                                                               a4.type,
                                                                               func)
                        else:
                            if(undef != 4):
                                astate = topol.BondedParams.get_dihedral_param(a1.type,
                                                                               a2.type,
                                                                               a3.type,
                                                                               a4.type,
                                                                               func)
                        # if types_morphe([a1,a2,a3,a4]):
                        if (undef != 3):
                                bstate = topol.BondedParams.get_dihedral_param(a1.typeB,
                                                                               a2.typeB,
                                                                               a3.typeB,
                                                                               a4.typeB,
                                                                               func)

                        if undef == 1 and astate == []:
                            continue
                        elif undef == 1 and (astate[0][0] == 4 or astate[0][0] == 2):
                            continue
                        elif undef == 2 and bstate == []:
                            continue
                        elif undef == 2 and (bstate[0][0] == 4 or bstate[0][0] == 2):
                            continue

                        # need to check if the dihedral has torsion pre-defined
                        counter = check_dih_ILDN_OPLS(topol, rlist, rdic,
                                                      a1, a2, a3, a4)

                        # torsion for both states defined, change nothing
                        if counter == 42:
                            continue

                        # A state disappears (when going to B)
                        for ast in astate:
                            if counter == 0:
                                d[5] = ast
                                if ast[0] == 3:
                                    bst = [ast[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                                elif ast[0] == 2:
                                    bst = [ast[0], ast[1], 0.0]
                                else:
                                    bst = [ast[0], ast[1], 0.0, ast[-1]]
                                if len(d) == 6:
                                    d.append(bst)
                                else:
                                    d[6] = bst
                                counter = 1
                            elif counter == 1 or counter == 3:
                                alus = backup_d[:]
                                alus[5] = ast
                                if ast[0] == 3:
                                    bst = [ast[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                                elif ast[0] == 2:
                                    bst = [ast[0], ast[1], 0.0]
                                else:
                                    bst = [ast[0], ast[1], 0.0, ast[-1]]

                                alus.append(bst)
                                dih9.append(alus)

                        # B state disappears (when going to A)
                        # all must go to the new (appendable) dihedrals
                        for bst in bstate:
                            if counter == 0:
                                if bst[0] == 3:
                                    ast = [bst[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                                elif bst[0] == 2:
                                    ast = [bst[0], bst[1], 0.0]
                                else:
                                    ast = [bst[0], bst[1], 0.0, bst[-1]]
                                d[5] = ast
                                if len(d) == 6:
                                    d.append(bst)
                                else:
                                    d[6] = bst
                                counter = 1
                            elif counter == 1 or counter == 2:
                                alus = backup_d[:]
                                if ast[0] == 3:
                                    ast = [bst[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                                elif ast[0] == 2:
                                    ast = [bst[0], bst[1], 0.0]
                                else:
                                    ast = [bst[0], bst[1], 0.0, bst[-1]]
                                alus[5] = ast
                                alus.append(bst)
                                dih9.append(alus)


                    if astate is None:
                        print 'Error: No dihedral angle found (state A: predefined state B) for:'
                        print a1.resname, a2.resname, a3.resname, a4.resname
                        print a1.name, a2.name, a3.name, a4.name, func
                        print a1.atomtype, a2.atomtype, a3.atomtype, a4.atomtype
                        print a1.type, a2.type, a3.type, a4.type
                        print a1.atomtypeB, a2.atomtypeB, a3.atomtypeB, a4.atomtypeB
                        print a1.typeB, a2.typeB, a3.typeB, a4.typeB
                        print astate
                        print d
                        sys.exit(1)

                    if bstate is None:
                        print 'Error: No dihedral angle found (state B: predefined state A) for:'
                        print a1.resname, a2.resname, a3.resname, a4.resname
                        print a1.name, a2.name, a3.name, a4.name, func
                        print a1.atomtype, a2.atomtype, a3.atomtype, a4.atomtype
                        print a1.type, a2.type, a3.type, a4.type
                        print a1.atomtypeB, a2.atomtypeB, a3.atomtypeB, a4.atomtypeB
                        print a1.typeB, a2.typeB, a3.typeB, a4.typeB
                        print d
                        sys.exit(1)

                    # the previous two if sentences will kill the execution
                    # if anything goes wrong. Therefore, I am not afraid to do
                    # d.append() already in the previous steps


    topol.dihedrals.extend(dih9)
    print('log_> Making dihedrals for state B -> %d dihedrals with perturbed atoms' % count)
    print('log_> Removed %d fake dihedrals' % nfake)


def get_torsion_multiplicity(name):
    foo = list(name)
    mult = int(foo[-1])
    return mult


def explicit_defined_dihedrals(filename, ff):
    """ get the #define dihedral entries explicitly for ILDN
    """
    l = open(filename).readlines()
    output = {}
    ffnamelower = ff.lower()
    for line in l:
        if line.startswith('#define'):
            entr = line.split()
            name = entr[1]
            if ffnamelower.startswith('amber'):
                params = [9, float(entr[2]), float(entr[3]), int(entr[4])]
            elif ffnamelower.startswith('opls'):
                if len(entr) == 8:  # dihedral
                    params = [3, float(entr[2]), float(entr[3]), float(entr[4]),
                              float(entr[5]), float(entr[6]), float(entr[7])]
                elif len(entr) == 5:
                    params = [1, float(entr[2]), float(entr[3]), float(entr[4])]
            output[name] = params
    return output


def is_ildn_dih_encountered(ildn_used, d, encountered):
    for dih in ildn_used:
        if (dih[0] == d[0] and dih[1] == d[1] and dih[2] == d[2]
           and dih[3] == d[3] and dih[4] == d[4]):
            encountered = 1
    return encountered


def find_predefined_dihedrals(topol, rlist, rdic, ffbonded,
                              dih_predef_default, ff):

    dih9 = []  # here I will accumulate multiple entries of type 9 dihedrals
    explicit_def = explicit_defined_dihedrals(ffbonded, ff)
    ildn_used = []  # ildn dihedrals that already were encountered
    opls_used = []  # opls dihedrals that already were encountered

    for r in rlist:
        idx = r.id - 1
        dih = rdic[r.resname][3]
        imp = rdic[r.resname][2]
        for d in imp+dih:
            al = []
            for name in d[:4]:
                if name.startswith('+'):
                    next = r.chain.residues[idx+1]
                    atom = next.fetch(name[1:])[0]
                    al.append(atom)
                elif name.startswith('-'):
                    prev = r.chain.residues[idx-1]
                    atom = prev.fetch(name[1:])[0]
                    al.append(atom)
                else:
                    atom = r.fetch(name)[0]
                    al.append(atom)

            for dx in topol.dihedrals:
                func = dx[4]
                if (dx[0].id == al[0].id and
                   dx[1].id == al[1].id and
                   dx[2].id == al[2].id and
                   dx[3].id == al[3].id) or \
                   (dx[0].id == al[3].id and
                   dx[1].id == al[2].id and
                   dx[2].id == al[1].id and
                   dx[3].id == al[0].id):
                    # the following checks are needed for amber99sb*-ildn
                    # do not overwrite proper (type9) with improper (type4)
                    if 'default-star' in d[4] and dx[4] == 9:
                        print('%s' % d[4])
                        continue
                    # is the dihedral already found for ILDN
                    encountered = 0
                    foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[4]]
                    encountered = is_ildn_dih_encountered(ildn_used, foobar, encountered)
                    foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[5]]
                    encountered = is_ildn_dih_encountered(ildn_used, foobar, encountered)
                    if encountered == 1:
                        continue
                    if 'tors' in d[4]:
                        if 'tors' not in dx[5]:
                            continue

                    # check for opls
                    encountered = 0
                    foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[4]]
                    encountered = is_ildn_dih_encountered(opls_used, foobar, encountered)
                    foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[5]]
                    encountered = is_ildn_dih_encountered(opls_used, foobar, encountered)
                    if encountered == 1:
                        continue
                    if 'dih_' in d[4]:
                        if 'dih_' not in dx[5]:
                            continue

                    A, B = check_case(al[:4])
                    paramA = topol.BondedParams.get_dihedral_param(al[0].type,
                                                                   al[1].type,
                                                                   al[2].type,
                                                                   al[3].type,
                                                                   func)
                    paramB = topol.BondedParams.get_dihedral_param(al[0].typeB,
                                                                   al[1].typeB,
                                                                   al[2].typeB,
                                                                   al[3].typeB,
                                                                   func)

                    astate = []
                    bstate = []
                    backup_dx = dx[:]
                    backup_dx2 = dx[:]

                    if d[4] == 'default-A':  # amber99sb
                        if 'un' in d[5]:
                            backup_dx2.append('undefB')
                        dih_predef_default.append(backup_dx2)
                        astate = paramA
                    elif d[4] == 'default-B':  # amber99sb
                        if 'un' in d[5]:
                            backup_dx2.append('undefB')
                        dih_predef_default.append(backup_dx2)
                        astate = paramB
                    elif d[4] == 'default-star':  # amber99sb*
                        foo = [4, 105.4, 0.75, 1]
                        astate.append(foo)
                    elif d[4].startswith('torsion_'):  # amber99sb-ildn
                        if 'un' in d[5]:
                            backup_dx2.append('undefB_ildn')
                        dih_predef_default.append(backup_dx2)
                        foo = explicit_def[d[4]]
                        astate.append(foo)
                        foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[4]]
                        ildn_used.append(foobar)
                        func = 9
                    elif d[4].startswith('dih_'):  # opls proper
                        if 'un' in d[5]:
                            backup_dx2.append('undefB')
                        dih_predef_default.append(backup_dx2)
                        foo = explicit_def[d[4]]
                        astate.append(foo)
                        foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[4]]
                        opls_used.append(foobar)
                        func = 3
                    elif d[4].startswith('improper_'):  # opls improper
                        if 'un' in d[5]:
                            backup_dx2.append('undefB')
                        dih_predef_default.append(backup_dx2)
                        foo = explicit_def[d[4]]
                        astate.append(foo)
                        foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[4]]
                        opls_used.append(foobar)
                        func = 1
                    elif 'un' in d[4]:  # amber99sb-ildn and opls and others
                        if d[5].startswith('torsion_'):
                            backup_dx2.append('undefA_ildn')
                        else:
                            backup_dx2.append('undefA')
                        dih_predef_default.append(backup_dx2)
                        astate = ''
                    else:
                        astate = d[4]

                    if d[5] == 'default-A':  # amber99sb
                        bstate = paramA
                    elif d[5] == 'default-B':  # amber99sb
                        bstate = paramB
                    elif d[5] == 'default-star':  # amber99sb*
                        foo = [4, 105.4, 0.75, 1]
                        bstate.append(foo)
                    elif d[5].startswith('torsion_'):  # amber99sb-ildn
                        foo = explicit_def[d[5]]
                        bstate.append(foo)
                        foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[5]]
                        ildn_used.append(foobar)
                        func = 9
                    elif d[5].startswith('dih_'):  # opls proper
                        foo = explicit_def[d[5]]
                        bstate.append(foo)
                        foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[5]]
                        opls_used.append(foobar)
                        func = 3
                    elif d[5].startswith('improper_'):  # opls improper
                        foo = explicit_def[d[5]]
                        bstate.append(foo)
                        foobar = [dx[0].id, dx[1].id, dx[2].id, dx[3].id, d[5]]
                        ildn_used.append(foobar)
                        func = 1
                    elif 'un' in d[5]:  # amber99sb-ildn and opls and others
                        bstate = ''
                    else:
                        bstate = d[5]

                    # A state
                    counter = 0
                    for foo in astate:
                        if counter == 0:
                            dx[4] = func
                            dx[5] = foo
                            if(func == 3):
                                bar = [foo[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                            elif(func == 2):
                                bar = [foo[0], foo[1], 0.0]
                            else:
                                bar = [foo[0], foo[1], 0.0, foo[-1]]
                            dx.append(bar)
                        else:
                            alus = backup_dx[:]
                            alus[5] = foo
                            if func == 3:
                                bar = [foo[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                            elif(func == 2):
                                bar = [foo[0], foo[1], 0.0]
                            else:
                                bar = [foo[0], foo[1], 0.0, foo[-1]]
                            alus.append(bar)
                            dih9.append(alus)
                        counter = 1

                    # B state
                    for foo in bstate:
                        if counter == 0:
                            dx[4] = func
                            if(func == 3):
                                bar = [foo[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                            elif(func == 2):
                                bar = [foo[0], foo[1], 0.0]
                            else:
                                bar = [foo[0], foo[1], 0.0, foo[-1]]
                            dx[5] = bar
                            dx.append(foo)
                        else:
                            alus = backup_dx[:]
                            if(func == 3):
                                bar = [foo[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                            elif(func == 2):
                                bar = [foo[0], foo[1], 0.0]
                            else:
                                bar = [foo[0], foo[1], 0.0, foo[-1]]
                            alus[5] = bar
                            alus.append(foo)
                            dih9.append(alus)
                        counter = 1

    topol.dihedrals.extend(dih9)


def is_hybrid_residue(resname):
    if (resname in _perturbed_nucleotides or resname[1] == '2' or
       '2CM' in resname or 'CM2' in resname):  # special two letter cases
        return True
    else:
        return False


def _change_outfile_format(filename, ext):
    head, tail = os.path.split(filename)
    name, ex = os.path.splitext(tail)
    new_name = os.path.join(head, name+'.'+ext)
    return new_name


def get_hybrid_residue(residue_name, mtp_file='ffamber99sb.mtp',
                       version='old'):
    print('log_> Scanning database for %s ' % residue_name)
    resi, bonds, imps, diheds, rotdic = read_mtp_entry(residue_name,
                                                       filename=mtp_file,
                                                       version=version)
    if len(resi.atoms) == 0:
        raise mtpError("Hybrid residue %s not found in %s"
                       % (residue_name, mtp_file))
    return resi, bonds, imps, diheds, rotdic


def get_hybrid_residues(m, ff, version):
    rdic = {}
    rlist = []
    for res in m.residues:
        if is_hybrid_residue(res.resname):
            rlist.append(res)
            # get topol params for hybrid
            mtp_file = get_mtp_file(res, ff)
            mtp = get_hybrid_residue(res.resname, mtp_file, version)
            rdic[res.resname] = mtp
            hybrid_res = mtp[0]
            atom_names = map(lambda a: a.name, hybrid_res.atoms)
            atoms = res.fetchm(atom_names)
            for i, atom in enumerate(hybrid_res.atoms):
                atoms[i].atomtypeB = atom.atomtypeB
                atoms[i].qB = atom.qB
                atoms[i].mB = atom.mB
    return rlist, rdic


def __add_extra_DNA_RNA_impropers(topol, rlist, func_type, stateA, stateB):
    extra_impropers = []
    for r in rlist:
        if r.resname in ['DAT', 'DAC', 'DGC', 'DGT', 'RAU', 'RAC', 'RGC', 'RGU']:
            print('Adding extra improper dihedrals for residue %d-%s'
                  % (r.id, r.resname))
            alist = r.fetchm(['C1\'', 'N9', 'C8', 'DC2'])
            extra_impropers.append(alist)
            alist = r.fetchm(['C1\'', 'N9', 'C4', 'DC6'])
            extra_impropers.append(alist)
        elif r.resname in ['DTA', 'DTG', 'DCG', 'DCA', 'RUA', 'RUG', 'RCG', 'RCA']:
            print('Adding extra improper dihedrals for residue %d-%s'
                  % (r.id, r.resname))
            alist = r.fetchm(['C1\'', 'N1', 'C6', 'DC4'])
            extra_impropers.append(alist)
            alist = r.fetchm(['C1\'', 'N1', 'C2', 'DC8'])
            extra_impropers.append(alist)
    for imp in extra_impropers:
        imp.extend([func_type, [func_type]+stateA, [func_type]+stateB])
    topol.dihedrals += extra_impropers


# =============
# Input Options
# =============
def parse_options():
    parser = argparse.ArgumentParser(description='''
This script fills in the B state to a topology file (itp or top) according to
the hybrid residues present in the file. If you provide a top file with
include statemets, the script will run through the included itp files too.

You need to use this script after having mutated a structure file with pmx mutate,
and after having passed that mutated structure through pdb2gmx.
''')

    parser.add_argument('-p',
                        metavar='topol',
                        dest='intop',
                        type=str,
                        help='Input topology file (itp or top). '
                        'Default is "topol.top"',
                        default='topol.top')
    parser.add_argument('-o',
                        metavar='outfile',
                        dest='outfile',
                        type=str,
                        help='Output topology file. '
                        'Default is "pmxtop.top"',
                        default='pmxtop.top')
    parser.add_argument('-ff',
                        metavar='ff',
                        dest='ff',
                        type=str.lower,
                        help='Force field to use. If none is provided, \n'
                        'a list of available ff will be shown.',
                        default=None)
    parser.add_argument('--split',
                        dest='split',
                        help='Write two separate topologies for vdw and q '
                        'morphing.',
                        default=False,
                        action='store_true')
    parser.add_argument('--scale_mass',
                        dest='scale_mass',
                        help='Scale the masses of morphing atoms so that '
                        'dummies have a mass of 1.',
                        default=False,
                        action='store_true')

    args, unknown = parser.parse_known_args()

    # ff selection
    if args.ff is None:
        args.ff = ff_selection()

    return args


def fill_bstate(topol, ff):
    """Fills the bstate of a topology file containing pmx hybrid residues. This
    can be either a top or itp file. If the top file contains itp file via
    include statements, the function will iterate through all of them to look
    for hybrid residues.

    Parameters
    ----------
    topol : Topology
        input Topology instance.
    ff : str
        name of the force field to be used

    Returns
    -------
    pmxtop : Topology
        output Topology instance with bstates assigned
    """

    # ff setup
    ff_path = get_ff_path(ff)
    ffbonded_file = os.path.join(ff_path, 'ffbonded.itp')

    # -------------------------
    # Start working on topology
    # -------------------------
    pmxtop = deepcopy(topol)
    # create model with residue list
    m = Model(atoms=pmxtop.atoms)
    # use model residue list
    pmxtop.residues = m.residues
    # get list of hybrid residues and their params
    rlist, rdic = get_hybrid_residues(m=m, ff=ff, version='new')
    # correct b-states
    pmxtop.assign_fftypes()
    for r in rlist:
        print('log_> Hybrid Residue -> %d | %s ' % (r.id, r.resname))

    find_bonded_entries(pmxtop)
    find_angle_entries(pmxtop)
    dih_predef_default = []
    find_predefined_dihedrals(pmxtop, rlist, rdic, ffbonded_file,
                              dih_predef_default, ff)
    find_dihedral_entries(pmxtop, rlist, rdic, dih_predef_default)

    __add_extra_DNA_RNA_impropers(pmxtop, rlist, 1, [180, 40, 2], [180, 40, 2])

    print('log_> Total charge of state A = %.f' % pmxtop.get_qA())
    print('log_> Total charge of state B = %.f' % pmxtop.get_qB())

    # if prolines are involved, break one bond (CD-CG)
    # and angles X-CD-CG, CD-CG-X
    # and dihedrals with CD and CG
    proline_decouplings(pmxtop, rlist, rdic)
    # also decouple all dihedrals with [CD and N] and [CB and Calpha] for proline
    proline_dihedral_decouplings(pmxtop, rlist, rdic)

    return pmxtop


def write_split_top(pmxtop, outfile='pmxtop.top', scale_mass=False,
                    verbose=False):
    """Write three topology files to be used for three separate free energy
    calculations: charges off, vdw on, changes on. This can be useful when one
    wants to avoid using a soft-core for the electrostatic interactions

    Parameters
    ----------
    pmxtop : Topology
        Topology object with B states defined.
    outfile : str
        name of output topology file.
    scale_mass : bool
        whether to scale the masses of morphing atoms
    verbose : bool
        whether to print information or not

    Returns
    -------
    None
    """

    root, ext = os.path.splitext(outfile)
    out_file_qoff = root + '_qoff' + ext
    out_file_vdw = root + '_vdw' + ext
    out_file_qon = root + '_qon' + ext

    # get charge of states A/B for hybrid residues
    qA = pmxtop.get_hybrid_qA()
    qB = pmxtop.get_hybrid_qB()

    print '------------------------------------------------------'
    print 'log_> Creating splitted topologies............'
    print 'log_> Making "qoff" topology : "%s"' % out_file_qoff
    contQ = deepcopy(qA)
    pmxtop.write(out_file_qoff, stateQ='AB', stateTypes='AA', dummy_qB='off',
                scale_mass=scale_mass, target_qB=qA, stateBonded='AA',
                full_morphe=False)
    print 'log_> Charge of state A: %g' % pmxtop.qA
    print 'log_> Charge of state B: %g' % pmxtop.qB

    print '------------------------------------------------------'
    print 'log_> Making "vdw" topology : "%s"' % out_file_vdw
    contQ = deepcopy(qA)
    pmxtop.write(out_file_vdw, stateQ='BB', stateTypes='AB', dummy_qA='off',
                dummy_qB='off', scale_mass=scale_mass,
                target_qB=contQ, stateBonded='AB', full_morphe=False)
    print 'log_> Charge of state A: %g' % pmxtop.qA
    print 'log_> Charge of state B: %g' % pmxtop.qB
    print '------------------------------------------------------'

    print 'log_> Making "qon" topology : "%s"' % out_file_qon
    pmxtop.write(out_file_qon, stateQ='BB', stateTypes='BB', dummy_qA='off',
                dummy_qB='on', scale_mass=scale_mass, target_qB=qB,
                stateBonded='BB', full_morphe=False)
    print 'log_> Charge of state A: %g' % pmxtop.qA
    print 'log_> Charge of state B: %g' % pmxtop.qB
    print '------------------------------------------------------'


def main(args):

    top_file = args.intop
    outfile = args.outfile
    ff = args.ff
    scale_mass = args.scale_mass

    # if input is itp but output is top, rename output
    if top_file.split('.')[-1] == 'itp' and outfile.split('.')[-1] != 'itp':
        out_file = _change_outfile_format(outfile, 'itp')
        print 'log_> Setting outfile name to %s' % out_file

    # load topology
    if top_file.split('.')[-1] == 'itp':
        print 'log_> Reading input .itp file "%s""' % (top_file)
        topol = Topology(top_file, version='new', ff=ff)
    else:
        print 'log_> Reading input .top file "%s"' % (top_file)
        topol = Topology(top_file, version='new', ff=ff)

    # fill the B states
    pmxtop = fill_bstate(topol=topol, ff=ff)
    # write hybrid topology
    pmxtop.write(outfile, scale_mass=scale_mass)

    # separated topologies
    if args.split is True:
        write_split_top(pmxtop=pmxtop, outfile=outfile, scale_mass=scale_mass,
                        verbose=True)

    print('')
    print('b-states filled...........')
    print('')


def entry_point():
    args = parse_options()
    main(args)


if __name__ == '__main__':
    entry_point()
