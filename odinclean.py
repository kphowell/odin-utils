#!/usr/bin/env python

from __future__ import print_function

import sys
import argparse
import logging
from collections import OrderedDict

from xigt.codecs import xigtxml
from xigt import Item, Tier


def clean_corpus(xc):
    for igt in xc:
        raw_tier = None
        clean_tier = None
        for tier in igt:
            if tier.type == 'odin':
                if tier.attributes.get('state') == 'raw':
                    raw_tier = tier
                elif tier.attributes.get('state') == 'cleaned':
                    clean_tier = tier
        if raw_tier is None:
            logging.info(
                'No raw tier found for cleaning for IGT with id: {}'
                .format(str(igt.id))
            )
        elif clean_tier is not None:
            logging.warning(
                'Cleaned tier already found for IGT with id: {}'
                .format(str(igt.id))
            )
        else:
            add_cleaned_tier(igt, raw_tier)


def add_cleaned_tier(igt, raw_tier):
    clean_id = None
    # check if ID is available
    for c_id in ('c', 'oc', 'cleaned', 'odin-cleaned'):
        if igt.get(c_id) is None:
            clean_id = c_id
            break
    if clean_id is None:
        logging.warning(
            'No preset ID for cleaned tier was available for IGT with id: {}'
            .format(str(igt.id))
        )
    else:
        cleaned_items = clean_items(raw_tier, clean_id)
        tier = Tier(
            id=clean_id,
            type='odin',
            alignment=raw_tier.id,
            attributes={'state': 'cleaned'},
            items=cleaned_items
        )
        igt.append(tier)


def clean_items(raw_tier, clean_id):
    # first make copies of the original items
    cln_items = copy_items(raw_tier.items)
    # then execute the cleaning steps
    #cln_items = merge_diacritics(cln_items)
    cln_items = merge_lines(cln_items)

    for i, item in enumerate(cln_items):
        item.alignment = item.id  # do this first so it aligns to raw ID
        item.id = '{}{}'.format(clean_id, i + 1)  # now change id

    return cln_items


def copy_items(items):
    return [
        Item(id=item.id, type=item.type, alignment=item.alignment,
             content=item.content, segmentation=item.segmentation,
             attributes=item.attributes, text=item.text)
        for item in items
    ]


def merge_diacritics(items):
    """
    Use unicodedata's normalize function first to get combining
    diacritics instead of standalone ones, then for any combining
    diacritic see if it combines with a nearby character (where
    "combine" here means that the two can be normalized as a single
    character.
    """
    # this StackOverflow answer by bobince was very helpful:
    # http://stackoverflow.com/a/447047
    newitems = []
    for item in items:
        line = item.text
        if line.strip() == '':
            newitems.append(item)
            continue
        line = unicodedata.normalize('NFKD', line)
        # first remove inserted spaces before diacritics
        max_j = len(line) - 1
        line = ''.join(c for j, c in enumerate(line)
                       if c != ' ' or (j < max_j and
                                       unicodedata.combining(line[j+1])==0))
        # then combine diacritics with previous, then following chars if
        # they can be combined
        chars = [line[0]] # always append first char
        max_j = len(line) - 1 # need to recalc this
        for j, c in enumerate(line[1:]):
            # skipped first char, so counter needs to be incremented
            j += 1
            if unicodedata.combining(c):
                # a character x and combining character c have length 2,
                # but if they combine, they have length 1
                if j < max_j and \
                     len(unicodedata.normalize('NFC', line[j+1] + c)) == 1:
                    # just append
                    chars.append(unicodedata.normalize('NFC', line[j+1] + c))
                elif len(unicodedata.normalize('NFC', chars[-1] + c)) == 1:
                    # need to replace appended previous char
                    chars[-1] = unicodedata.normalize('NFC', chars[-1] + c)
            else:
                chars.append(c)
        # then check if combining diacritics match adjacent chars
        #for j, c in enumerate(line)
        item.text = ''.join(chars)
        newitems.append(item)
    return newitems


def merge_lines(items):
    """
    Return the lines with corrupted and split lines merged.
    Merge corrupted lines if:
      * Both lines have the +CR tag
      * Both lines have one other tag in common
      * The lines are sequential
      * tokens in one line align to whitespace in the other
    TODO:
      * Can we allow some non-whitespace overlap, in which case the
        token would be inserted in the closest match
      * Can we recombine diacritics with the letter it came from?
        E.g. is this usually accents or umlauts on vowels?
      * Is there anything that can be done about intraline corruption?
        E.g. when spaces are inserted w i t h i n words
    """
    n = len(items)
    # nothing to do if there's just 1 line
    if n < 2:
        return items
    newitems = [items[0]]
    for i in range(1,n):
        # lines are pairs of attributes and content
        prev = newitems[-1]
        cur = items[i]
        p_tags = prev.attributes.get('tag','').split('+')
        c_tags = cur.attributes.get('tag','').split('+')
        # if no non-CR tags are shared
        if 'CR' not in c_tags or \
           len(set(p_tags).intersection(c_tags).difference(['CR'])) == 0:
            newitems.append(cur)
            continue
        merged = bit_merge(prev.text or '', cur.text or '')
        if merged is not None:
            # there's no OrderedSet, but OrderedDict will do
            tags = OrderedDict((t,1) for t in p_tags + c_tags)
            line_nums = ' '.join([prev.attributes.get('line'),
                                  cur.attributes.get('line')])
            prev.attributes['tag'] = '+'.join(tags)
            prev.attributes['line'] = line_nums
            prev.text = merged
    return newitems


def merge_strings(a, b):
    maxlen = max([len(a), len(b)])
    a = a.ljust(maxlen)
    b = b.ljust(maxlen)
    m = []
    for i in range(maxlen):
        pass
        # do something like this
        #   "a a a"  "a a a"    "a a a"  "a a a"  "a a a"
        # + " b"     " bbb "    " b b "  "  b"    "  bb"
        # = "aba a"  "abbba a"  "ababa"  "a aba"  "a abba"

    return ''.join(m).rstrip(' ')


def bit_merge(a, b):
    """
    Merge two strings on whitespace by converting whitespace to the
    null character, then AND'ing the bit strings of a and b, then
    convert back to regular strings (with spaces).
    """
    if len(b) > len(a): return bit_merge(b, a)
    try:
        # get bit vectors with nulls instead of spaces, and
        # make sure the strings are the same length
        a = a.replace(' ','\0').encode('utf-8')
        b = b.replace(' ','\0').encode('utf-8').ljust(len(a), b'\0')
        c_pairs = zip(a, b)
    except UnicodeDecodeError:
        return None
    c = []
    for c1, c2 in c_pairs:
        # only merge if they merge cleanly
        if c1 != 0 and c2 != 0:
            return None
        else:
            c.append(c1|c2)
    try:
        return bytes(c).decode('utf-8').replace('\0',' ').rstrip(' ')
    except UnicodeDecodeError:
        return None



## ============================================= ##
## For running as a script rather than a library ##
## ============================================= ##

def main(arglist=None):
    class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter,
                        argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description="Clean ODIN 'raw' tiers",
        epilog='examples:\n'
            '    odinclean.py by-doc-id/10.xml\n'
            '    cat by-doc-id/10.xml | odinclean.py > 10-cleaned.xml'
    )
    parser.add_argument('-v', '--verbose',
        action='count', dest='verbosity', default=2,
        help='increase the verbosity (can be repeated: -vvv)'
    )
    parser.add_argument('infiles',
        nargs='*',
        help='the ODIN Xigt (XML) files to clean'
    )
    args = parser.parse_args(arglist)
    logging.basicConfig(level=50-(args.verbosity*10))
    run(args)


def run(args):
    if args.infiles:
        for fn in args.infiles:
            xc = xigtxml.load(fn, mode='full')
            clean_corpus(xc)
            xigtxml.dump(fn, xc)
    else:
        xc = xigtxml.load(sys.stdin, mode='full')
        clean_corpus(xc)
        print(xigtxml.dumps(xc))


if __name__ == '__main__':
    main()
