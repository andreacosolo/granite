#!/usr/bin/env python

#################################################################
#
#    qcVCF
#        Michele Berselli
#        Harvard Medical School
#        berselli.michele@gmail.com
#
#################################################################


#################################################################
#
#    LIBRARIES
#
#################################################################
import sys, os
import json
# shared_functions as *
from granite.lib.shared_functions import *
# vcf_parser
from granite.lib import vcf_parser
# pedigree_parser
from granite.lib import pedigree_parser


#################################################################
#
#    FUNCTIONS
#
#################################################################
#################################################################
#    General stats for variants
#################################################################
def get_stats(vnt_obj, stat_dict, ID_list):
    ''' extract information from variant for single samples,
    update counts for each sample in ID_list '''
    var_type = variant_type_ext(vnt_obj.REF, vnt_obj.ALT)
    for ID in ID_list:
        _genotype(vnt_obj, ID, var_type, stat_dict)
        if var_type == 'snv':
            _substitution(vnt_obj, ID, vnt_obj.REF, vnt_obj.ALT, stat_dict)
        #end if
    #end for
#end def

def _genotype(vnt_obj, ID, var_type, stat_dict):
    ''' genotype information, update counts for ID '''
    GT = vnt_obj.get_genotype_value(ID, 'GT').replace('|', '/')
    if GT not in ['0/0', './.']: # sample has variant
        alt, alt_ = GT.split('/')
        if alt == alt_:
            stat_dict[ID][var_type]['hom'] += 1
        else:
            stat_dict[ID][var_type]['het'] += 1
        #end if
        stat_dict[ID][var_type]['tot'] += 1
    #end if
#end def

def _substitution(vnt_obj, ID, REF, ALT, stat_dict):
    ''' substitution information, update counts for ID '''
    GT = vnt_obj.get_genotype_value(ID, 'GT').replace('|', '/')
    if GT not in ['0/0', './.']: # sample has variant
        stat_dict[ID]['sub'][REF + '>' + ALT] += 1
    #end if
#end def

#################################################################
#    Pedigree stats
#################################################################
def get_stats_pedigree(pedigree_obj, vnt_obj, stat_dict, ID_list):
    ''' extract information from variant for pedigree,
    update counts for each sample in ID_list '''
    var_type = variant_type_ext(vnt_obj.REF, vnt_obj.ALT)
    for ID in ID_list:
        _mendelian_error(pedigree_obj, vnt_obj, ID, var_type, stat_dict)
    #end for
#end def

def _mendelian_error(pedigree_obj, vnt_obj, ID, var_type, stat_dict):
    ''' check for mendelian error based on trio information,
    update counts for ID '''
    GT, parents_GT = vnt_obj.get_genotype_value(ID, 'GT').replace('|', '/'), []
    if GT not in ['0/0', './.']: # sample has variant
        parents = pedigree_obj.get_member_by_sample(ID).get_parents()
        if len(parents) < 2: return # missing trio information, skip variant
        #end if
        for parent in parents:
            if not parent.is_sample(): # missing parent sample information,
                return                 # skip variant
            #end if
            try:
                GT_ = vnt_obj.get_genotype_value(parent.sample, 'GT').replace('|', '/')
            except Exception: return # parent sample missing in vcf, skip variant
            #end try
            if GT_ == './.':
                if GT in ['0/1', '1/0']:
                    stat_dict[ID]['trio'][var_type]['het']['miss'] += 1
                    stat_dict[ID]['trio'][var_type]['het']['tot'] += 1
                elif GT == '1/1':
                    stat_dict[ID]['trio'][var_type]['hom']['miss'] += 1
                    stat_dict[ID]['trio'][var_type]['hom']['tot'] += 1
                #end if
                return # missing genotype for parent, skip
            #end if
            parents_GT.append(GT_)
        #end for
        GT_0, GT_1 = parents_GT[0], parents_GT[1]
        # Check errors
        if GT in ['0/1', '1/0']:
            if GT_0 == '0/0' and GT_1 == '0/0':
                stat_dict[ID]['trio'][var_type]['het']['de_novo'] += 1
                stat_dict[ID]['trio'][var_type]['het']['tot'] += 1
            elif GT_0 == '1/1' and GT_1 == '1/1':
                stat_dict[ID]['trio'][var_type]['het']['errors'] += 1
                stat_dict[ID]['trio'][var_type]['het']['tot'] += 1
            #end if
        elif GT == '1/1':
            if GT_0 == '0/0' or GT_1 == '0/0':
                stat_dict[ID]['trio'][var_type]['hom']['errors'] += 1
                stat_dict[ID]['trio'][var_type]['hom']['tot'] += 1
            #end if
        #end if
    #end if
#end def

#################################################################
#
#################################################################
def tt_ratio(sub_dict):
    ''' return transition-transversion ratio'''
    ti = sub_dict['A>G'] + sub_dict['G>A'] + sub_dict['T>C'] + sub_dict['C>T']
    tv = sub_dict['A>T'] + sub_dict['T>A'] + sub_dict['A>C'] + sub_dict['C>A'] \
        + sub_dict['G>T'] + sub_dict['T>G'] + sub_dict['G>C'] + sub_dict['C>G']
    return ti / tv
#end def

def to_json(stat_dict, stat_to_add):
    ''' '''
    stat_json = {}
    if 'ti_tv' in stat_to_add:
        stat_json.setdefault('transition-transversion ratio', [])
    #end if
    if 'het_hom' in stat_to_add:
        stat_json.setdefault('heterozygosity ratio', {
                                               'SNV': [], 'INS': [],
                                               'DEL': [], 'MNV': []
                                           })
    #end if
    if 'trio_errors' in stat_to_add:
        stat_json.setdefault('mendelian errors in trio', {
                                               'SNV': [], 'INS': [],
                                               'DEL': []
                                           })
    #end if
    for ID in stat_dict:
        for k, v in stat_dict[ID].items():
            tmp_dict = {}
            # heterozygosity ratio
            if k in ['snv', 'ins', 'del', 'mnv'] and 'het_hom' in stat_to_add:
                tmp_dict.setdefault('name', ID)
                if v['hom']:
                    hh_ratio = round(v['het'] / v['hom'], 2)
                    tmp_dict.setdefault('ratio', hh_ratio)
                #end if
                tmp_dict.setdefault('counts', v)
                stat_json['heterozygosity ratio'][k.upper()].append(tmp_dict)
            #end if
            # substitutions
            if k == 'sub' and 'ti_tv' in stat_to_add:
                tmp_dict.setdefault('name', ID)
                try: tmp_dict.setdefault('ratio', round(tt_ratio(v), 2))
                except Exception: pass
                #end try
                tmp_dict.setdefault('counts', v)
                stat_json['transition-transversion ratio'].append(tmp_dict)
            #end if
            # mendelian errors trio
            if k == 'trio' and 'trio_errors' in stat_to_add:
                for k_v, v_v in v.items():
                    tmp_dict = {} # reset tmp_dict
                    if k_v in ['snv', 'ins', 'del']:
                        if v_v['het']['tot'] or v_v['hom']['tot']:
                            tmp_dict.setdefault('name', ID)
                            tmp_dict.setdefault('counts', v_v)
                            stat_json['mendelian errors in trio'][k_v.upper()].append(tmp_dict)
                        #end if
                    #end if
                #end for
            #end if
        #end for
    #end for
    return stat_json
#end def

#################################################################
#    runner
#################################################################
def main(args):
    ''' '''
    # Variables
    is_verbose = True if args['verbose'] else False
    stat_dict = {}
    stat_to_add = []

    # Check command line arguments
    if args['ti_tv']: stat_to_add.append('ti_tv')
    #end if
    if args['het_hom']: stat_to_add.append('het_hom')
    #end if
    if args['trio_errors']: stat_to_add.append('trio_errors')
    #end if
    if not stat_to_add:
        sys.exit('\nERROR in parsing arguments: specify at least one metric to add\n')
    #end if

    # Buffers
    fo = open(args['outputfile'], 'w')

    # Creating Vcf object
    vcf_obj = vcf_parser.Vcf(args['inputfile'])

    # Get list of sample IDs to use
    ID_list = args['samples'] # list of sample IDs

    # Loading pedigree
    if os.path.isfile(args['pedigree']):
        with open(args['pedigree']) as fi:
            pedigree = json.load(fi)
        #end with
    else:
        try: pedigree = json.loads(args['pedigree'])
        except Exception:
            sys.exit('\nERROR in parsing arguments: pedigree must be either a json file or a string representing a json\n')
        #end try
    #end if

    # Creating Pedigree object
    pedigree_obj = pedigree_parser.Pedigree(pedigree)

    # Initializing stat_dict
    for ID in ID_list:
        stat_dict.setdefault(ID, {
                            'snv': {'het': 0, 'hom': 0, 'tot': 0},
                            'ins': {'het': 0, 'hom': 0, 'tot': 0},
                            'del': {'het': 0, 'hom': 0, 'tot': 0},
                            'mnv': {'het': 0, 'hom': 0, 'tot': 0},
                            'mav': {'het': 0, 'hom': 0, 'tot': 0},
                            'sub': {
                                'A>G': 0, 'A>T': 0, 'A>C': 0,
                                'T>A': 0, 'T>G': 0, 'T>C': 0,
                                'C>A': 0, 'C>G': 0, 'C>T': 0,
                                'G>A': 0, 'G>T': 0, 'G>C': 0
                                },
                            'trio': {
                                'snv': {
                                        'het': {'de_novo': 0, 'errors': 0, 'miss': 0, 'tot': 0},
                                        'hom': {'errors': 0, 'miss': 0, 'tot': 0}
                                        },
                                'ins': {
                                        'het': {'de_novo': 0, 'errors': 0, 'miss': 0, 'tot': 0},
                                        'hom': {'errors': 0, 'miss': 0, 'tot': 0}
                                        },
                                'del': {
                                        'het': {'de_novo': 0, 'errors': 0, 'miss': 0, 'tot': 0},
                                        'hom': {'errors': 0, 'miss': 0, 'tot': 0}
                                        },
                                'mnv': {
                                        'het': {'de_novo': 0, 'errors': 0, 'miss': 0, 'tot': 0},
                                        'hom': {'errors': 0, 'miss': 0, 'tot': 0}
                                        },
                                'mav': {
                                        'het': {'de_novo': 0, 'errors': 0, 'miss': 0, 'tot': 0},
                                        'hom': {'errors': 0, 'miss': 0, 'tot': 0}
                                        }
                                }
                            })
    #end for

    # Reading variants
    analyzed = 0
    for i, vnt_obj in enumerate(vcf_obj.parse_variants(args['inputfile'])):
        if is_verbose:
            sys.stderr.write('\rAnalyzing variant... ' + str(i + 1))
            sys.stderr.flush()
        #end if

        # # Check if chromosome is canonical and in valid format
        # if not check_chrom(vnt_obj.CHROM):
        #     continue
        # #end if
        analyzed += 1

        # Getting and updating stats
        get_stats(vnt_obj, stat_dict, ID_list)
        get_stats_pedigree(pedigree_obj, vnt_obj, stat_dict, ID_list)
    #end for

    # Writing output
    sys.stderr.write('\n\n...Writing results for ' + str(analyzed) + ' analyzed variants out of ' + str(i + 1) + ' total variants\n')
    sys.stderr.flush()

    # Create json
    stat_json = to_json(stat_dict, stat_to_add)

    # Write json to file
    json.dump(stat_json, fo, indent=2, sort_keys=False)

    # Closing buffers
    fo.close()
#end def


#################################################################
#
#    MAIN
#
#################################################################
if __name__ == "__main__":

    main()

#end if