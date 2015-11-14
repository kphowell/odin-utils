#!/usr/bin/env python

import sys
import os
import re
from collections import defaultdict
import argparse
import logging

from xigt.codecs import xigtxml
from xigt import XigtCorpus, xigtpath as xp

by_paths = {
    'lang': 'metadata//dc:subject/@olac:code',
    'doc-id': '@doc-id',
}

def run(args):
    create_outdir(args.outdir)
    idx = defaultdict(lambda: defaultdict(set))  # key : filename : igt-index
    by = by_paths[args.by]
    for fn in args.infiles:
        logging.info('Indexing {}'.format(fn))
        index(fn, by, idx)
    for key, fn_idx in idx.items():
        logging.info('Writing {} (grouped from {} files)'
                     .format(key, len(fn_idx)))
        if key is None:
            key = '---'
        out_fn = os.path.join(args.outdir, key.replace(':', '-') + '.xml')
        write(out_fn, fn_idx)

def create_outdir(outdir):
    if os.path.isdir(outdir):
        logging.error('Output directory already exists.')
        sys.exit(1)
    try:
        os.mkdir(outdir)
    except OSError:
        logging.error('Output directory could not be created.')
        sys.exit(1)


def index(fn, by, idx):
    xc = xigtxml.load(fn, mode='transient')
    for i, igt in enumerate(xc):
        idx_key = xp.find(igt, by)
        idx[idx_key][fn].add(i)

def write(out_fn, fn_idx):
    xc = XigtCorpus()
    for fn, igt_indices in fn_idx.items():
        in_xc = xigtxml.load(fn, mode='transient')
        # ignoring corpus-level metadata (we don't use it in ODIN 2.1)
        for i, igt in enumerate(in_xc):
            if i in igt_indices:
                xc.append(igt)
    # Within a corpus, we want to sort IGTs by doc-id
    # warning: non-API member _list might break in future versions of Xigt
    xc._list.sort(key=igt_sort_key)
    #xc.refresh_index()
    # assume the nsmap of the first igt is the same for all
    if xc.igts: xc.nsmap = xc[0].nsmap
    xigtxml.dump(out_fn, xc)

def igt_sort_key(igt):
    try:
        skey = (int(igt.get_attribute('doc-id', default=0)),
                int(re.sub(r'^(igt|i)([^-]+-)?', '', igt.id or '0-0')))
    except ValueError:
        skey = (0, 0)
    return skey

def main(arglist=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Group ODIN IGTs into corpora by language or doc-id",
        epilog='examples:\n'
            '    odingroup.py --by=lang by-lang by-doc-id/*.xml'
    )
    parser.add_argument('-v', '--verbose',
        action='count', dest='verbosity', default=2,
        help='increase the verbosity (can be repeated: -vvv)'
    )
    parser.add_argument('outdir',
        help='the output directory for files of grouped instances'
    )
    parser.add_argument('infiles',
        nargs='*',
        help='the ODIN Xigt (XML) files to group instances from'
    )
    parser.add_argument('--by',
        choices=('lang', 'doc-id'), required=True,
        help='the attribute to group IGT instances by'
    )
    args = parser.parse_args(arglist)
    logging.basicConfig(level=50-(args.verbosity*10))
    run(args)

if __name__ == '__main__':
    import cProfile
    cProfile.run('main()', 'restats')
    #main()
