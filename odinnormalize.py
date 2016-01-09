#!/usr/bin/env python

from __future__ import print_function

import sys
import re
import argparse
import logging

from xigt.codecs import xigtxml
from xigt import Item, Tier


BLANK_TAG = 'B'

def normalize_corpus(xc):
    for igt in xc:
        base_tier = None
        norm_tier = None
        for tier in igt:
            if tier.type == 'odin':
                state = tier.attributes.get('state')
                # don't get raw tier if cleaned exists
                if base_tier is None and state == 'raw':
                    base_tier = tier
                elif state == 'cleaned':
                    base_tier = tier
                elif state == 'normalized':
                    norm_tier = tier
        if base_tier is None:
            logging.info(
                'No cleaned tier found for normalizing for IGT with id: {}'
                .format(str(igt.id))
            )
        elif norm_tier is not None:
            logging.warning(
                'Normalized tier already found for IGT with id: {}'
                .format(str(igt.id))
            )
        else:
            add_normalized_tier(igt, base_tier)


def add_normalized_tier(igt, base_tier):
    norm_id = None
    # check if ID is available
    for n_id in ('n', 'on', 'normalized', 'odin-normalized'):
        if igt.get(n_id) is None:
            norm_id = n_id
            break
    if norm_id is None:
        logging.warning(
            'No preset ID for normalized tier was available '
            'for IGT with id: {}'
            .format(str(igt.id))
        )
    else:
        norm_items = normalize_items(base_tier, norm_id)
        tier = Tier(
            id=norm_id,
            type='odin',
            alignment=base_tier.id,
            attributes={'state': 'normalized'},
            items=norm_items
        )
        igt.append(tier)


def normalize_items(base_tier, norm_id):
    # first make copies of the original items
    nrm_items = copy_items(base_tier.items)
    remove_blank_items(nrm_items)  # don't even bother with blank lines

    for item in nrm_items:
        # and set the copy's alignments to their current ID (changed later)
        item.alignment = item.id

        if item.text is None or item.text.strip() == '':
            item.text = ''  # why wasn't this labeled as a blank line?
            continue

        remove_quotes(item)
        remove_surrounding_parens(item)
        remove_example_numbers(item)
        remove_precontent_tags(item)
        rejoin_hyphenated_grams(item)
        extract_judgment(item)

    for i, item in enumerate(nrm_items):
        item.id = '{}{}'.format(norm_id, i + 1)

    return nrm_items


def copy_items(items):
    return [
        Item(id=item.id, type=item.type, alignment=item.alignment,
             content=item.content, segmentation=item.segmentation,
             attributes=item.attributes, text=item.text)
        for item in items
    ]


def remove_blank_items(items):
    return [
        i for i in items
        if i.attributes.get('tag') != BLANK_TAG
        or (i.text or '').strip() != ''
    ]


paren_re = re.compile(r'\([^)]*\)')


def remove_quotes(item):
    # remove spaces, quotes, and punctuation to make later regexes simpler
    item.text = item.text.strip().strip('"\'`')


def remove_surrounding_parens(item):
    # only strip initial parens if on both sides (so we don't turn 'abc (def)'
    # into 'abc (def'
    line = item.text
    if line.startswith('(') and line.endswith(')'):
        line = line[1:-1]
    # space, quote, and punc strip, in case the parens grouped them
    line = line.strip().strip('"\'`')
    item.text = line


paren_num_re = re.compile(
    r"^\(\s*(" # start (X; ( X; group for alternates
    r"[\d.]+\w?|\w|" # 1 1a 1.a 1.23.4b; a b (no multiple chars, except...)
    r"[ivxlc]+)"    # roman numerals: i iv xxiii; end alt group
    r"['.:]*\s*\)[.:]*") # optional punc (X) (X:) (X') (X.) (X. ) (X). (X):
num_re = re.compile(
    r"^([\d.]+\w?|\w|[ivxlc]+)" # nums w/no parens; same as above
    r"['.):]+\s" # necessary punc; 1. 1' 1) 1: 10.1a. iv: etc.
)


def remove_example_numbers(item):
    # IGT-initial numbers (e.g. '1.' '(1)', '5a.', '(ii)')
    line = item.text
    line = paren_num_re.sub('', line).strip()
    line = num_re.sub('', line).strip()
    item.text = line


def remove_precontent_tags(item):
    # precontent tags can be 1 or 2 words ("intended:" or "speaker", "a:")
    # ignore those with 3 or more
    item.text = re.sub(r'^\s*\w+(\s\w+)?\s*:\s', '', item.text)


def rejoin_hyphenated_grams(item):
    # there may be morphemes separated by hyphens, but with intervening
    # spaces; remove those spaces (e.g. "dog-  NOM" => "dog-NOM")
    item.text = re.sub(r'\s*-\s*', '-', item.text)

# judgment extraction adapted from code from Ryan Georgi (PC)
# don't attempt for still-corrupted lines or those with alternations
# (detected by looking for '/' in the string)
def extract_judgment(item):
    if 'CR' in item.attributes.get('tag','').split('+'):
        return
    match = re.match(r'^\s*([*?#]+)[^/]+$', item.text)
    if match:
        item.attributes['judgment'] = match.group(1)
    item.text = re.sub(r'^(\s*)[*?#]+\s*', r'\1', item.text)

## ============================================= ##
## For running as a script rather than a library ##
## ============================================= ##

def main(arglist=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Normalize ODIN 'clean' tiers",
        epilog='examples:\n'
            '    odinnormalize.py by-doc-id/10.xml\n'
            '    cat 10-clean.xml | odinnormalize.py > 10-norm.xml'
    )
    parser.add_argument('-v', '--verbose',
        action='count', dest='verbosity', default=2,
        help='increase the verbosity (can be repeated: -vvv)'
    )
    parser.add_argument('infiles',
        nargs='*',
        help='the ODIN Xigt (XML) files to normalize'
    )
    args = parser.parse_args(arglist)
    logging.basicConfig(level=50-(args.verbosity*10))
    run(args)


def run(args):
    if args.infiles:
        for fn in args.infiles:
            xc = xigtxml.load(fn, mode='full')
            normalize_corpus(xc)
            xigtxml.dump(fn, xc)
    else:
        xc = xigtxml.load(sys.stdin, mode='full')
        normalize_corpus(xc)
        print(xigtxml.dumps(xc))


if __name__ == '__main__':
    main()
