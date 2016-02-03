#!/usr/bin/env python

from __future__ import print_function

import sys
import re
import argparse
import logging
try:
    from itertools import izip_longest as zip_longest  # py2
except ImportError:
    from itertools import zip_longest  # py3

from xigt.codecs import xigtxml
from xigt import Item, Tier, xigtpath as xp


BLANK_TAG = 'B'
LANG_CODE_PATH = 'metadata//dc:subject/@olac:code'
LANG_NAME_PATH = 'metadata//dc:subject/text()'

# quote list: https://en.wikipedia.org/wiki/Quotation_mark
QUOTES = (
    '\u0022'  # quotation mark (")
    '\u0027'  # apostrophe (')
    '\u00ab'  # left-pointing double-angle quotation mark
    '\u00bb'  # right-pointing double-angle quotation mark
    '\u2018'  # left single quotation mark
    '\u2019'  # right single quotation mark
    '\u201a'  # single low-9 quotation mark
    '\u201b'  # single high-reversed-9 quotation mark
    '\u201c'  # left double quotation mark
    '\u201d'  # right double quotation mark
    '\u201e'  # double low-9 quotation mark
    '\u201f'  # double high-reversed-9 quotation mark
    '\u2039'  # single left-pointing angle quotation mark
    '\u203a'  # single right-pointing angle quotation mark
    '\u300c'  # left corner bracket
    '\u300d'  # right corner bracket
    '\u300e'  # left white corner bracket
    '\u300f'  # right white corner bracket
    '\u301d'  # reversed double prime quotation mark
    '\u301e'  # double prime quotation mark
    '\u301f'  # low double prime quotation mark
    '\ufe41'  # presentation form for vertical left corner bracket
    '\ufe42'  # presentation form for vertical right corner bracket
    '\ufe43'  # presentation form for vertical left corner white bracket
    '\ufe44'  # presentation form for vertical right corner white bracket
    '\uff02'  # fullwidth quotation mark
    '\uff07'  # fullwidth apostrophe
    '\uff62'  # halfwidth left corner bracket
    '\uff63'  # halfwidth right corner bracket
)
# note: adding grave accent (`) and comma (,) as they've been observed
#       serving as quotes
QUOTEPAIRS = {
    '\u0022': ['\u0022'],  # quotation mark (")
    '\u0027': ['\u0027'],  # apostrophe (')
    '\u002c': ['\u0027', '\u0060'],  # comma/(apostrophe|grave-accent)
    '\u0060': ['\u0027'],  # grave-accent/apostrophe
    '\u00ab': ['\u00bb'],  # left/right-pointing double-angle quotation mark
    '\u00bb': ['\u00ab', '\u00bb'],  # right/(left|right)-pointing double-angle quotation mark
    '\u2018': ['\u2019'],  # left/right single quotation mark
    '\u2019': ['\u2019'],  # right single quotation mark
    '\u201a': ['\u201b', '\u2018', '\u2019'],  # single low-9/(high-reversed-9|left-single|right-single) quotation mark
    '\u201b': ['\u2019'],  # single high-reversed-9/right-single quotation mark
    '\u201c': ['\u201d'],  # left/right double quotation mark
    '\u201d': ['\u201d'],  # right double quotation mark
    '\u201e': ['\u201c', '\u201d'],  # double-low-9/(left-double|right-double) quotation mark
    '\u201f': ['\u201d'],  # double-high-reversed-9/right-double quotation mark
    '\u2039': ['\u203a'],  # single left/right-pointing angle quotation mark
    '\u203a': ['\u2039', '\u203a'],  # single right/(left|right)-pointing angle quotation mark
    '\u300c': ['\u300d'],  # left/right corner bracket
    '\u300e': ['\u300f'],  # left/right white corner bracket
    '\u301d': ['\u301e'],  # reversed/* double prime quotation mark
    '\u301f': ['\u301e'],  # low/* double prime quotation mark
    '\ufe41': ['\ufe42'],  # presentation form for vertical left/right corner bracket
    '\ufe43': ['\ufe44'],  # presentation form for vertical left/right corner white bracket
    '\uff02': ['\uff02'],  # fullwidth quotation mark
    '\uff07': ['\uff07'],  # fullwidth apostrophe
    '\uff62': ['\uff63']  # halfwidth left/right corner bracket
}
OPENQUOTES = ''.join(QUOTEPAIRS.keys())
CLOSEQUOTES = ''.join(q for qs in QUOTEPAIRS.values() for q in qs)

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
    items = copy_items(base_tier.items)
    items = remove_blank_items(items)  # don't bother with blank lines
    items = rejoin_continuations(items)
    items = rejoin_translations(items)
    items = remove_citations(items)
    items = remove_language_name(items, base_tier.igt)
    items = remove_example_numbers(items)
    items = remove_blank_items(items)  # in case previous created blanks

    for item in items:
        # and set the copy's alignments to their current ID (changed later)
        item.alignment = item.id
        rejoin_hyphenated_grams(item)
        extract_judgment(item)

    items = separate_secondary_translations(items)
    items = dewrap_lines(items)
    items = unquote_translations(items)
    items = shift_left(items)

    for i, item in enumerate(items):
        item.id = '{}{}'.format(norm_id, i + 1)

    return items


def copy_items(items):
    return [
        Item(id=item.id, type=item.type,
             attributes=item.attributes, text=item.text)
        for item in items
    ]


def get_tags(item):
    return item.attributes.get('tag', '').split('+')

def whitespace(m):
    start, end = m.span()
    return ' ' * (end - start)

def remove_blank_items(items):
    return [
        i for i in items
        if (i.text or '').strip() != ''
    ]


def merge_items(*items):
    alignment = ','.join(i.alignment for i in items if i.alignment)
    content = ','.join(i.content for i in items if i.content)
    segmentation = ','.join(i.segmentation for i in items if i.segmentation)

    if segmentation and (alignment or content):
        raise ValueError(
            'Cannot merge items defining segmentation and another '
            'reference attribute.'
        )

    base = items[0]

    base.text = ' '.join(i.text for i in items)

    base.attributes['line'] = ' '.join(i.attributes['line'] for i in items)
    if alignment: base.alignment = alignment
    if content: base.content = content
    if segmentation: base.segmentation = segmentation

    pri_tags = set()
    sec_tags = set()
    for item in items:
        tags = get_tags(item)
        if tags[0]:
            pri_tags.add(tags[0])
        sec_tags.update(tags[1:])
    tag = '-'.join(sorted(pri_tags)).replace('G-L', 'L-G')
    if sec_tags:
        tag = '{}+{}'.format(tag, '+'.join(sorted(sec_tags)))
    base.attributes['tag'] = tag


def rejoin_continuations(items):
    new_items = []
    for item in items:
        tags = get_tags(item)
        if tags[0] == 'C' and new_items:
            item.text = item.text.lstrip()
            item.attributes['tag'] = item.attributes['tag'][1:]  # remove C
            merge_items(new_items[-1], item)
        else:
            new_items.append(item)
    return new_items


def rejoin_translations(items):
    # rejoin translation lines if they don't start with some kind of
    # speaker indicator, quote, or other
    new_items = []
    prev_is_t = False
    for item in items:
        tags = get_tags(item)
        is_t = tags[0] == 'T' and 'DB' not in tags and 'CR' not in tags
        marked = re.match(r'^\s*[(\[]?\s*\S+\s*\.?\s*[)\]]?\s*:', item.text)
        if prev_is_t and is_t and not marked:
            item.text = item.text.lstrip()
            merge_items(new_items[-1], item)
        else:
            new_items.append(item)
            prev_is_t = is_t
    return new_items


citation_re = re.compile(
    r'=?'
    '('
    r'\[(?P<inner1>([^)]*(\([^)]*\))?)[0-9]*([^)]*(\([^)]*\))?))\]'
    r'|'
    r'\((?P<inner2>([^)]*(\([^)]*\))?)[0-9]*([^)]*(\([^)]*\))?))\)'
    ')'
    r'\s*$'
)

def remove_citations(items):
    def removable(m, t, i):
        # citation matches are removable if they don't look like
        # translation alternates or bracketed glosses
        if t in ('L', 'G'):
            start, end = m.span()
            other = None
            if t == 'L':  # look down then up for nearest G
                others = items[i+1:] + items[i-1::-1]
                t2 = 'G'
            else:  # look up then down for nearest L
                others = items[i-1:] + items[i-1::-1]
                t2 = 'L'
            other = next((i for i in others if get_tags(i)[0] == t2), None)
            if other and (other.text or '')[start:end].strip() != '':
                return False
        elif re.match(r'\s*[{}].*[{}]\s*$'.format(OPENQUOTES, CLOSEQUOTES),
                      m.group('inner1') or m.group('inner2')):
            return False
        return True

    for i, item in enumerate(items):
        tags = get_tags(item)
        if tags[0] not in ('L', 'G', 'T', 'L-G', 'L-T', 'L-G-T'):
            continue
        match = citation_re.search(item.text)
        if (match and removable(match, tags[0], i)):
            meta_item = Item(id=item.id,
                             text=match.group(0).strip(),
                             attributes=item.attributes)
            m_tags = ['M']
            item.text = citation_re.sub('', item.text).rstrip()
            if 'AC' in tags:
                tags.remove('AC')
                m_tags.append('AC')
            elif 'LN' in tags:
                tags.remove('LN')
                m_tags.append('LN')
            elif 'CN' in tags:
                tags.remove('CN')
                m_tags.append('CN')
            # what about other tags? LN, CN, EX
            item.attributes['tag'] = '+'.join(tags)
            meta_item.attributes['tag'] = '+'.join(m_tags)
            items.append(meta_item)
    return items


def remove_language_name(items, igt):
    new_items = []
    lgcode = xp.find(igt, LANG_CODE_PATH)
    lgname = xp.find(igt, LANG_NAME_PATH)
    lgtoks = []
    if lgcode and '?' not in lgcode and '*' not in lgcode:
        lgtoks.append(lgcode)
        lgtoks.extend(lgcode.split(':'))  # split up complex codes
    if lgname and '?' not in lgname:
        lgtoks.append(lgname)
        if re.search('[- ]', lgname):  # abbreviation for multiword names
            lgtoks.append(''.join(ln[0] for ln in re.split(r'[- ]+', lgname)))
        if re.search(r'^\w{3}', lgname):
            lgtoks.append(lgname[:3])
    if lgtoks:
        sig = '|'.join(re.escape(t) for t in lgtoks)
        start_lg_re = re.compile(r'^\s*[(\[]?({})[)\]]?'.format(sig), re.I)
        end_lg_re = re.compile(r'[(\[]?({})[)\]]?\s*$'.format(sig), re.I)
        for item in items:
            tags = get_tags(item)
            if tags[0] == 'M':
                new_items.append(item)
            else:
                orig = item.text
                m = start_lg_re.match(item.text)
                if m:
                    meta_item = Item(id=item.id,
                                     text=m.group(0).strip(),
                                     attributes=dict(item.attributes))
                    meta_item.attributes['tag'] = 'M+LN'
                    new_items.append(meta_item)
                    item.text = start_lg_re.sub(whitespace, item.text)
                m = end_lg_re.search(item.text)
                if m:
                    meta_item = Item(id=item.id,
                                     text=m.group(0).strip(),
                                     attributes=dict(item.attributes))
                    meta_item.attributes['tag'] = 'M+LN'
                    items.append(meta_item)
                    item.text = end_lg_re.sub(whitespace, item.text).rstrip()
                if 'LN' in tags and item.text != orig:
                    tags.remove('LN')
                item.attributes['tag'] = '+'.join(tags)
                new_items.append(item)
    else:
        new_items = items
    return new_items


ex_num_re = re.compile(
    '^(?P<exnum>'
    r'\s*'
    r'(?P<paren>[(\[])?\s*'
    r'(?P<pre>ex|\w)?'
    r'(?(pre)[\d.]+|([\d.]+\w?|\w|[ivxlc]+))'
    r'(?(paren)[\'.]*|[\'.)])'
    r'(?(paren)\s*[)\]])'
    ')'  # end exnum
    r'\s',
    re.I
)


def remove_example_numbers(items):
    # IGT-initial numbers (e.g. '1.' '(1)', '5a.', '(ii)')
    def removable(m):
        start, end = m.span()
        end -= 1 # ignore the required final space
        mtext = m.group('exnum')
        for item in items:
            tags = get_tags(item)
            if tags[0] not in ('L', 'G', 'T', 'L-G', 'G-T', 'L-T', 'L-G-T'):
                continue
            text = (item.text or '')[start:end]
            if text != mtext and text.strip() != '':
                return False
        return True

    for item in items:
        tags = get_tags(item)
        if tags[0] in ('L-G', 'L-T', 'G-T', 'L-G-T'):
            item.text = ex_num_re.sub(whitespace, item.text)
        elif tags[0] in ('L', 'G', 'T'):
            m = ex_num_re.match(item.text)
            while m and removable(m):
                item.text = ex_num_re.sub(whitespace, item.text)
                m = ex_num_re.match(item.text)
    return items


# def remove_precontent_tags(item):
#     # precontent tags can be 1 or 2 words ("intended:" or "speaker", "a:")
#     # ignore those with 3 or more
#     item.text = re.sub(r'^\s*\w+(\s\w+)?\s*:\s', '', item.text)


def rejoin_hyphenated_grams(item):
    # there may be morphemes separated by hyphens, but with intervening
    # spaces; slide the token over (e.g. "dog-  NOM" => "dog-NOM  ")
    text = item.text
    toks = []
    pos = 0
    for match in list(re.finditer(r'(\S*(?:\s*[-=.]\s*\S*)+)', text)):
        start, end = match.span()
        toks.append(text[pos:start])
        toks.append(text[start:end].replace(' ', ''))
        pos = end
    toks.append(text[pos:len(text)])
    item.text = ''.join(toks).rstrip()

# judgment extraction adapted from code from Ryan Georgi (PC)
# don't attempt for still-corrupted lines or those with alternations
# (detected by looking for '/' in the string)
def extract_judgment(item):
    tags = get_tags(item)
    if tags[0] == 'M' or 'CR' in tags:
        return
    match = re.match(r'^\s*([*?#]+)[^/]+$', item.text)
    if match:
        item.attributes['judgment'] = match.group(1)
    item.text = re.sub(r'^(\s*)[*?#]+\s*', r'\1', item.text)


lit_trans_re = re.compile(
    r'\s*(?P<pri>.*?)\s*'
    '(?P<sec>'
    # no parens, must have "lit:"
    r'(?P<lit1>lit(?:eral(?:ly)?)?\s*[,.:]+)\s*'
    r'[{openquotes}](?P<s1>.*)[{closequotes}]'
    r'|'  # parens only around "lit" (open quotes on either side)
    r'[{openquotes}]?'
    r'\((?P<lit2>lit(?:eral(?:ly)?)?\s*[,.:]*)\)\s*'
    r'[{openquotes}]?\s*(?P<s2>.*)[{closequotes}]'
    r'|'  # with parens, "lit" optional
    r'[(\[]\s*'
    r'(?P<lit3>lit(?:eral(?:ly)?)?\s*[,.:]*)?\s*'
    r'[{openquotes}](?P<s3>.*)[{closequotes}]\s*'
    r'[)\]]'
    r'\s*(?P<pri_close>[closequotes])?'
    #r'(P<rest>.*)$'  # this breaks things?
    ')'  # end sec
    r'\s*$'
    .format(openquotes=OPENQUOTES, closequotes=CLOSEQUOTES),
    re.I
)
alt_trans_re = re.compile(
    r'(?P<pri>.*[.?!{closequotes}])'
    r'\s*/\s*(?P<lit1>lit(?:eral(?:ly)?)?\s*[,.:]*)?\s*'
    r'(?P<s1>.*)'
    .format(closequotes=CLOSEQUOTES),
    re.I
)


def separate_secondary_translations(items):
    # sometimes translation lines with secondary translations are marked
    # as +DB even if they are for the same, single IGT
    for item in items:
        tags = get_tags(item)
        if tags[0] in ('L', 'G', 'L-G') and 'DB' in tags[1:]:
            # don't attempt
            return items
    # find non-double secondary translations and split if necessary, then
    # normalize the tags
    new_items = []
    for item in items:
        tags = get_tags(item)
        if tags[0] == 'T' and 'CR' not in tags[1:]:
            m = lit_trans_re.match(item.text)
            if not m and item.text.count('/') == 1:
                m = alt_trans_re.search(item.text)
            if m:
                get = lambda k: m.groupdict().get(k) or ''
                pri = get('pri') + get('pri_close')
                sec = get('s1') or get('s2') or get('s3') or ''
                if pri:
                    item.text = pri
                    pritags = [t for t in tags if t not in ('LT', 'AL')]
                    item.attributes['tag'] = '+'.join(pritags)
                    new_items.append(item)
                sec_item = Item(
                    id=item.id,
                    attributes=item.attributes,
                    text=sec
                )
                is_lit = bool(get('lit1') or get('lit2') or get('lit3'))
                sec_tags = tags
                if is_lit and 'LT' not in sec_tags:
                    sec_tags.append('LT')
                elif 'AL' not in sec_tags:
                    sec_tags.append('AL')
                sec_item.attributes['tag'] = '+'.join(sec_tags)
                new_items.append(sec_item)
            else:
                new_items.append(item)
        else:
            new_items.append(item)
    return new_items


def dewrap_lines(items):
    # look for patterns like L G L G and join them to L G
    # then look for T T and join them to T if they don't look like alternates
    unwrapped = []
    used = set()
    sig = []
    for item in items:
        tags = get_tags(item)
        if tags[0] in ('L', 'G', 'T'):
            sig.append(item.attributes['tag'])
    sig = ' '.join(sig)
    if (any(x in sig for x in ('L G L G ', 'L G T L G T', 'G G ', 'L L '))
        and not any(x in sig for x in ('L+', 'L-', 'G+', 'G-'))):
        # likely patterns for wrapping without other noise
        ls = [item for item in items if item.attributes.get('tag') == 'L']
        gs = [item for item in items if item.attributes.get('tag') == 'G']
        for l_, g_ in zip_longest(ls, gs):
            if l_ is not None and g_ is not None:
                maxlen = max([len(l_.text), len(g_.text)])
                l_.text = l_.text.ljust(maxlen)
                g_.text = g_.text.ljust(maxlen)
        if ls:
            merge_items(*ls)
            unwrapped.append(ls[0])
        if gs:
            merge_items(*gs)
            unwrapped.append(gs[0])
        used.update(id(x) for x in ls + gs)
    # add everything unused up to the first translation
    for item in items:
        if item.attributes.get('tag') in ('T', 'T+AC'):
            break
        elif id(item) not in used:
            unwrapped.append(item)
            used.add(id(item))
    # now do translations
    if (any(x in sig for x in ('L G T L G T', 'T T+AC', 'T T+LN', 'T T'))
        and not any(x in sig for x in ('+EX', '+LT', '+AL', 'T+CR'))):
        # translations that appear wrapped and not alternates
        ts = [item for item in items
              if item.attributes.get('tag') in ('T', 'T+AC', 'T+LN')]
        if ts:
            merge_items(*ts)
            unwrapped.append(ts[0])
        used.update(id(x) for x in ts)
    # finally add anything unused
    for item in items:
        if id(item) not in used:
            unwrapped.append(item)
            used.add(id(item))
    return unwrapped


def unquote_translations(items):
    for item in items:
        tags = get_tags(item)
        if tags[0] == 'T':
            item.text = re.sub(r'^\s*[{}]'.format(OPENQUOTES), '', item.text)
            item.text = re.sub(r'[{}]\s*$'.format(CLOSEQUOTES), '', item.text)
    return items


def shift_left(items):
    # don't shift left T lines; they get done separately.
    shiftable_tags = ('L', 'G', 'L-G', 'G-T', 'L-T', 'L-G-T')
    indents = []
    for item in items:
        tags = get_tags(item)
        if tags[0] in shiftable_tags:
            indents.append(len(re.match(r'^\s*', item.text).group(0)))
    if indents:
        maxshift = min(indents)
        for item in items:
            tags = get_tags(item)
            if tags[0] in shiftable_tags:
                item.text = item.text[maxshift:]
            elif tags[0] == 'M':
                item.text = item.text.strip()
    return items


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
            logging.info('Normalizing {}'.format(fn))
            xc = xigtxml.load(fn, mode='full')
            normalize_corpus(xc)
            xigtxml.dump(fn, xc)
    else:
        xc = xigtxml.load(sys.stdin, mode='full')
        normalize_corpus(xc)
        print(xigtxml.dumps(xc))


if __name__ == '__main__':
    main()
