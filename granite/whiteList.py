#!/usr/bin/env python

#################################################################
#
#    whiteList
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
# shared_functions as *
from granite.lib.shared_functions import *
# vcf_parser
from granite.lib import vcf_parser


#################################################################
#
#    FUNCTIONS
#
#################################################################
def check_VEP(vnt_obj, idx, VEPremove, VEPrescue):
    ''' '''
    try: val_get = vnt_obj.get_tag_value('VEP')
    except Exception:
        sys.exit('\nERROR in whitelist check: VEP tag missing for variant:\n\t{0}\n'
                    .format(vnt_obj.to_string()))
    #end try
    trscrpt_list = val_get.split(',')
    is_whitelist = len(trscrpt_list)
    # Get all terms
    for trscrpt in trscrpt_list:
        # & is standard VEP format, but cgap use ~
        trscrpt_terms = set(trscrpt.split('|')[idx].replace('~', '&').split('&'))
        if trscrpt_terms.intersection(VEPrescue):
            break
        elif trscrpt_terms.intersection(VEPremove):
            is_whitelist -= 1
        else: break
        #end if
    #end for
    if is_whitelist:
        return True
    #end if
    return False
#end def

def check_spliceAI(vnt_obj, thr=0.8):
    ''' check if SpliceAI tag value is over threshold thr '''
    try: val_get = float(vnt_obj.get_tag_value('SpliceAI'))
    except Exception: return False
    #end try
    if val_get >= thr:
        return True
    #end if
    return False
#end def

def check_CLINVAR(vnt_obj):
    ''' check if CLINVAR tag is present '''
    try: val_get = vnt_obj.get_tag_value('CLINVAR')
    except Exception: return False
    #end try
    return True
#end def

#################################################################
#    runner
#################################################################
def main(args):
    ''' '''
    # Variables
    VEPremove = {'intron_variant', 'intergenic_variant',
                 'downstream_gene_variant', 'upstream_gene_variant',
                 'regulatory_region_variant'}
    VEPrescue, consequence_idx = {}, 0
    BED_bitarrays = {}
    is_VEP = True if args['VEP'] else False
    is_CLINVAR = True if args['CLINVAR'] else False
    SpliceAI_thr = float(args['SpliceAI']) if args['SpliceAI'] else 0.
    is_BEDfile = True if args['BEDfile'] else False

    # Buffers
    fo = open(args['outputfile'], 'w')

    # Creating Vcf object
    vcf_obj = vcf_parser.Vcf(args['inputfile'])

    # Writing header
    fo.write(vcf_obj.header.definitions)
    fo.write(vcf_obj.header.columns)

    # VEP
    if is_VEP:
        consequence_idx = vcf_obj.header.get_tag_field_idx('VEP', 'Consequence')
        if args['VEPrescue']: VEPrescue = {term for term in args['VEPrescue']}
        #end if
        if args['VEPremove']: VEPremove.update({term for term in args['VEPremove']})
        #end if
    elif args['VEPrescue'] or args['VEPremove']:
        sys.exit('\nERROR in parsing arguments: specify the flag "--VEP" to filter by VEP annotations to apply rescue terms or remove additional terms\n')
    #end if

    # BED
    if is_BEDfile:
        BED_bitarrays = bed_to_bitarray(args['BEDfile'])
    #end if

    # Reading variants and writing passed
    analyzed = 0
    for i, vnt_obj in enumerate(vcf_obj.parse_variants(args['inputfile'])):
        sys.stderr.write('\rAnalyzing variant... ' + str(i + 1))
        sys.stderr.flush()

        # # Check if chromosome is canonical and in valid format
        # if not check_chrom(vnt_obj.CHROM):
        #     continue
        # #end if
        analyzed += 1

        # Check BED
        if is_BEDfile:
            try: # CHROM and POS can miss in the BED file, if that just pass to next checks
                if BED_bitarrays[vnt_obj.CHROM][vnt_obj.POS]:
                    fo.write(vnt_obj.to_string())
                    continue
                #end if
            except Exception: pass
            #end try
        #end if

        # Check VEP
        if is_VEP:
            if check_VEP(vnt_obj, consequence_idx, VEPremove, VEPrescue):
                fo.write(vnt_obj.to_string())
                continue
            #end if
        #end if

        # Check SpliceAI
        if SpliceAI_thr:
            if check_spliceAI(vnt_obj, SpliceAI_thr):
                fo.write(vnt_obj.to_string())
                continue
            #end if
        #end if

        # Check CLINVAR
        if is_CLINVAR:
            if check_CLINVAR(vnt_obj):
                fo.write(vnt_obj.to_string())
                continue
            #end if
        #end if
    #end for
    sys.stderr.write('\n\n...Wrote results for ' + str(analyzed) + ' analyzed variants out of ' + str(i + 1) + ' total variants\n')
    sys.stderr.flush()

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