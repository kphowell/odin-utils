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
`odin` tiers if a raw tier exists and a cleaned tier doesn't. This can
either be run like a filter, which takes a single corpus on stdin and
prints to stdout:

```sh
cat 10.xml | odinclean.py > 10-cleaned.xml
```

Or it can be run with filename arguments, in which case the files are
modified in-place:

```sh
odinclean.py ~/odin-2.1/data/by-doc-id/*.xml
```

## odinnormalize.py

This module behaves just like `odinclean.py`, but it normalizes the
text contents of the cleaned tier, if available, or else the raw tier.

```sh
cat 10-cleaned.xml | odinnormalize.py > 10-normalized.xml
```

or

```sh
odinnormalize.py ~/odin-2.1/data/by-doc-id/*.xml
```


[Xigt]: http://depts.washington.edu/uwcl/xigt
