#! /usr/bin/env python

from __future__ import print_function

import os
import re
import argparse
import logging
from collections import defaultdict


buffer_size = 1000  # How many IGTs to cache before writing to the file
default_split_key = '_ungrouped_'

### READING ODIN TEXT ##################################################

doc_re = re.compile(r'doc_id=(?P<doc_id>\S+) '
                    r'(?:igt_id=(?P<igt_id>\S+) )?'
                    r'(?P<linerange>\d+ \d+) '
                    r'(?P<linetypes>.*)')

def odin_blocks(lines):
    line_iterator = iter(lines)
    for line in line_iterator:
        doc = doc_re.match(line)
        if doc is None:
            if 'doc_id=' in line:
                logging.warning('Possible ODIN instance missed: {}'
                                .format(line))
            continue

        header_lines = []
        lang = None
        iso639 = None
        odin_lines = []

        try:
            while line.strip() != '' and not line.startswith('line='):
                header_lines.append(line.rstrip())
                line = next(line_iterator)

            lang, iso639 = get_best_lang_match(header_lines)
            log_comments(
                doc.group('doc_id'), doc.group('linerange'),
                header_lines
            )
            if lang is None or iso639 is None:
                logging.warning('Failed to get language or language code for '
                                'document {}, lines {}.'
                                .format(doc.group('doc_id'),
                                        doc.group('linerange')))
            else:
                logging.debug('Document {}, lines {}, Language: {}, '
                              'ISO-639-3: {}'
                              .format(doc.group('doc_id'),
                                      doc.group('linerange'),
                                      lang, iso639))

            while line.strip() != '':
                odin_lines.append(odin_line(line))
                line = next(line_iterator)

        except StopIteration:
            pass

        finally:
            yield {
                'doc_id': doc.group('doc_id'),
                'igt_id': doc.group('igt_id'),
                'line_range': doc.group('linerange'),
                'line_types': doc.group('linetypes'),
                'language': lang,
                'iso-639-3': iso639,
                'lines': odin_lines,
                'header_lines': header_lines
            }


lang_chosen_re = re.compile(r'(?P<name>.*) \((?P<iso639>[^)]+)\)\s*$',
                            re.UNICODE)
stage2_LN_re = re.compile(r'stage2_LN_lang_code: (?P<name>.*) '
                          r'\([^,]+, (?P<iso639>[^)]+)\)')
chosen_idx_re = re.compile(r'lang_chosen_idx=(?P<idx>[-0-9]+)')


def get_best_lang_match(lines):
    lang_lines = dict(l.split(':', 1) for l in lines if ':' in l)
    # find best match
    match = None
    for key in ('language', 'stage3_lang_chosen', 'stage2_lang_chosen'):
        if key in lang_lines:
            match = lang_chosen_re.search(lang_lines[key])
            if match:
                break
    if match is None:
        if 'stage2_LN_lang_code' in lang_lines:
            first = lang_lines['stage2_LN_lang_code'].split('||', 1)[0]
            match = stage2_LN_re.match(first)
        elif 'lang_code' in lang_lines and \
             'lang_chosen_idx' in lang_lines['note']:
            prematch = chosen_idx_re.search(lang_lines['note'])
            if prematch:
                idx = int(prematch.group('idx'))
                if idx != -1:
                    langstring = lang_lines['lang_code'].split('||')[idx]
                    match = lang_chosen_re.match(langstring)
    if match:
        return (match.group('name').strip().title(),
                match.group('iso639').strip().lower())
    else:
        return ('(Undetermined)', 'und')


def log_comments(doc_id, linerange, lines):
    comment_keys = ('comments', 'stage2_comment', 'not_an_IGT')
    comments = [
        line for line in lines
        if ':' in line and line.split(':', 1)[0] in comment_keys
    ]
    if comments:
        logging.info(
            'doc_id={} lines={} has annotator comments:\n'
            .format(doc_id, linerange) +
            '  ' + '\n  '.join(comments)
        )


line_re = re.compile(r'line=(?P<line>\d+) tag=(?P<tag>[^:]+):(?P<content>.*)')


def odin_line(line):
    match = line_re.match(line)
    if match:
        return {
            'line': match.group('line'),
            'tag': match.group('tag'),
            'content': match.group('content')
        }
    else:
        logging.warning('Non-empty IGT line could not be parsed:\n{}'
                        .format(line))
        return {}


## ============================================= ##
## For running as a script rather than a library ##
## ============================================= ##

def main(arglist=None):
    class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter,
                        argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description="Read ODIN text data and output",
        epilog='examples:\n'
            '    odintxt.py --assign-igt-ids by-doc-id original/*.txt\n'
            '    odintxt.py --split-by=language by-lang by-doc-id/*.txt'
    )
    parser.add_argument('-v', '--verbose',
        action='count', dest='verbosity', default=2,
        help='increase the verbosity (can be repeated: -vvv)'
    )
    # parser.add_argument('-M', '--file-meta',
    #     choices=('keep', 'discard'), default='discard',
    #     help='how to handle file-level metadata'
    # )
    parser.add_argument('-m', '--igt-meta',
        choices=('keep', 'discard'), default='discard',
        help='how to handle igt-level metadata'
    )
    parser.add_argument('--assign-igt-ids',
        action='store_true',
        help='assign unique IDs to each IGT'
    )
    parser.add_argument('--first-id',
        metavar='N', type=int, default=1,
        help='the index of the first ID'
    )
    parser.add_argument('-s', '--split-by',
        choices=('doc_id', 'iso-639-3'), default='doc_id',
        help='group IGTs by their doc_id|language'
    )
    parser.add_argument('outdir', help='the directory for output files')
    parser.add_argument('infiles',
        nargs='*',
        help='the ODIN text files to read (if none, read from stdin)'
    )
    args = parser.parse_args(arglist)
    args.file_meta = 'discard'  # remove if --file-meta is enabled above
    logging.basicConfig(level=50-(args.verbosity*10))
    run(args)


class _BufferedIGTWriter(object):
    """
    Buffer grouped IGTs so we don't open the file to write every time.
    """
    def __init__(self, outdir):
        self.outdir = outdir
        self.cache = defaultdict(list)
    def write(self, key, igt):
        self.cache[key].append(igt)
        if len(self.cache[key]) >= buffer_size:
            self.flush(key)
    def flush(self, key=None):
        if key is None:
            keys = list(self.cache.keys())
        else:
            keys = [key]
        for key in keys:
            path = key.replace(':', '-') + '.txt'
            with open(os.path.join(self.outdir, path), 'a') as f:
                for igt in self.cache[key]:
                    print(format_odin_igt(igt), file=f, end='\n\n')
            del self.cache[key]


def format_odin_igt(igt):
    # now choose top line based on existence of igt_id field
    if 'igt_id' in igt:
        top = 'doc_id={doc_id} igt_id={igt_id} {line_range} {line_types}'
    else:
        top = 'doc_id={doc_id} {line_range} {line_types}'
    lang_line = 'language: {language} ({iso-639-3})'
    line = 'line={line} tag={tag}:{content}'
    lines = [top.format(**igt), lang_line.format(**igt)]
    for hl in igt['header_lines']:
        if not hl.startswith('language:'):  # don't put language line twice
            lines.append(hl)
    for linedata in igt['lines']:
        lines.append(line.format(**linedata))
    return '\n'.join(lines)


def run(args):
    if not os.path.exists(args.outdir):
        os.mkdir(args.outdir)  # raises OSError, e.g., if dir exists
    writer = _BufferedIGTWriter(args.outdir)
    # either go through all files or just read from stdin
    if args.infiles:
        for fn in args.infiles:
            with open(fn, 'r') as f:
                process(f, writer, args)
    else:
        process(sys.stdin, writer, args)
    writer.flush()


def process(f, writer, args):
    for i, igt in enumerate(odin_blocks(f)):
        if args.assign_igt_ids:
            igt['igt_id'] = 'igt{}-{}'.format(
                igt['doc_id'],
                args.first_id + i
            )
        if args.igt_meta == 'discard':
            igt['header_lines'] = []
        key = igt.get(args.split_by, default_split_key)
        writer.write(key, igt)


if __name__ == '__main__':
    main()
