#!/usr/bin/env python

from collections import defaultdict, OrderedDict
import logging


def load_citations(fn):
    db = defaultdict(OrderedDict)
    docid = None
    for i, line in enumerate(open(fn)):
        line = line.strip()
        if not line:
            docid = None
        elif line.startswith('doc_id'):
            _, docid = line.split('=')
            docid = docid.strip()
        elif docid is None:
            logging.warning('Property at line {} has no doc-id'.format(i+1))
        else:
            key, val = line.split(':', 1)
            db[docid][key.strip()] = val.strip()
    return db


def load_update_tsv(fn):
    db = defaultdict(OrderedDict)
    with open(fn) as f:
        fields = next(f).split()
        for i, line in enumerate(f):
            toks = line.split('\t')
            docid = toks[0].strip()
            if not docid:
                logging.warning(
                    'Update line {} is missing a doc-id.'.format(i+2)
                )
            for key, val in zip(fields[1:], toks[1:]):
                db[docid][key.strip()] = val.strip()
    return db


def update(db, newvals, add=False):
    for docid, d in newvals.items():
        if docid not in db and add == False:
            continue
        else:
            for key, val in d.items():
                db[docid][key] = val


def print_citations(db):
    def safe_int(i):
        try:
            return int(i)
        except ValueError:
            return i
    for docid in sorted(db, key=safe_int):
        print('doc_id={}'.format(docid))
        for key, val in db[docid].items():
            print('{}: {}'.format(key, val))
        print()


def run(args):
    db = load_citations(args.file)
    if args.update:
        update(db, load_update_tsv(args.update), add=args.insert_missing)
    # filtering
    print_citations(db)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose',
        action='count', dest='verbosity', default=2,
        help='increase the verbosity (can be repeated: -vvv)'
    )
    parser.add_argument('file',
        help='a citations.txt file'
    )
    parser.add_argument('--update',
        metavar='FILE',
        help='a tab-separated file of values to update'
    )
    parser.add_argument('--insert-missing',
        action='store_true',
        help='allow update to create new entries'
    )
    args = parser.parse_args()
    logging.basicConfig(level=50-(args.verbosity*10))
    run(args)
