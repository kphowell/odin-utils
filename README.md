# ODIN Utils

This repository contains a collection of utilities and Python modules
for working with ODIN data, in text format or in [Xigt][].

## odintxt.py

The `odintxt.py` module is for reading and writing the original text
format of the ODIN data. It also contains functions for interpreting
the metadata, assigning IGT IDs, and splitting the data by either
document ID or language.

The usage is `odintxt.py [OPTIONS] output-directory [input-files...]`

For example:

```sh
odintxt.py --assign-igt-ids txt-by-doc-id/ ~/odin-txt-files/*.txt
odintxt.py --split-by iso-639-3 txt-by-lang/ txt-by-doc-id/*.txt
```

Some tips:
* instead of normal filename expansion for input files, use
  `` `ls txt-files/*.txt -v` `` to sort them by numeric doc_id order
  (so `10.txt` comes after `9.txt` and not `109.txt`)
* for a doc_id and iso-639-3 split to have consistent `igt_id` values,
  use `--assign-igt-ids` on the first run, then use the output of that
  run for the second one (as shown in the example above)
* use a higher logging level (`-v`) to get log messages about
  annotator comments (going up two logging levels (`-vv`) is probably
  overkill unless you're debugging)

## odinclean.py

This module takes a XigtXML-formatted ODIN corpus and adds cleaned
`odin` tiers if a raw tier exists and a cleaned tier doesn't. Cleaning
currently only merges lines with the `+CR` tag if tokens on one line
lines align with whitespace on the other and the lines share the same
tags.

This can either be run like a filter, which takes a single corpus on
stdin and prints to stdout:

```sh
cat 10.xml | odinclean.py > 10-cleaned.xml
```

Or it can be run with filename arguments, in which case the files are
modified in-place:

```sh
odinclean.py ~/odin-2.1/data/by-doc-id/xigt/*.xml
```

## odinnormalize.py

This module behaves just like `odinclean.py`, but it normalizes the
text contents of the cleaned tier, if available, or else the raw tier.
Normalization does a number of things:

* rejoins continued lines (`tag="C"`)
* rejoins wrapped translation lines
* extracts citations (and other kinds of parenthesized metadata) from
  L, G, and T lines and puts it in a new M line
* extracts language names (based on the language name and code
  metadata) to a new M line
* removes example numbers
* rejoins hyphenated grams on the L and G lines (e.g. `dog -s`
  becomes `dog-s`)
* extracts judgment markers (like `*` or `#`) to a judgment attribute
* separates secondary translations (e.g. `` `...' (Lit. `...') ``)
* dewraps L and G lines
* unquotes translation lines
* de-indents all lines consistently (keeping column alignments)
* removes blank items

```sh
cat 10-cleaned.xml | odinnormalize.py > 10-normalized.xml
```

or

```sh
odinnormalize.py ~/odin-2.1/data/by-doc-id/xigt/*.xml
```

## rmtiers.sh

`rmtiers.sh` script will take a tier ID as its first argument and
remove all tiers with that ID from given files. E.g., to remove all
normalized tiers (presumably with `id="n"`)

```sh
rmtiers.sh n ~/odin-2.1/data/by-doc-id/xigt/*.xml
```

## citations.py

This script is for updating the citations.txt file that accompanies
an ODIN release. It can be used to update the database with new
information provided via a tab-separated-value file.

```sh
citations.py --update new-values.tsv citations.txt
```

## odin_lookup.txt
This file contains an abbreviated table of grams and their “gold” 
concepts that were extracted from the ODIN database. 

The citation for this tag set is:

William Lewis and Fei Xia, 2010. Developing ODIN: A Multilingual 
Repository of Annotated Language Data for Hundreds of the World's 
Languages, Journal of Literary and Linguistic Computing (LLC), 
25(3):303-319.

## odin_lexicon.txt
This file contains a list of generic grams as well as an expanded set 
of grams identified in particular papers for particular languages, 
extracted from the ODIN database.

The citation for this tag set is:

William Lewis and Fei Xia, 2010. Developing ODIN: A Multilingual 
Repository of Annotated Language Data for Hundreds of the World's 
Languages, Journal of Literary and Linguistic Computing (LLC), 
25(3):303-319.

[Xigt]: http://depts.washington.edu/uwcl/xigt
