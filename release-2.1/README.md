
# ODIN 2.1 Release Script

This directory contains the script for generating the ODIN 2.1
release data. It requires a number of software packages:

- [Xigt v1.1](https://github.com/xigt/xigt/releases/tag/v1.1.0)
- [Odin-Utils](https://github.com/xigt/odin-utils) (this repository)
- [INTENT v0.6](https://github.com/rgeorgi/intent)

The script also written for Bash on Linux, so it might not be portable
to other shells or platforms.

## Configuration

A file called `config.bash` contains the parameters for configuring
the release script for your local platform. There are a number of
variables that probably need to be defined:

Parameter    | Description
------------ | -----------------------------------------------------------
`TXTDIR`     | Path to the original ODIN text data
`RELEASEDIR` | Path for the output release data
`PYTHON`     | The locally installed Python3.3+ version (e.g. `python3.4`)
`XIGTHOME`   | Path to the local clone of the Xigt v1.1 repository
`INTENT`     | Path to the INTENT command (`intent.py`)

## Basic Execution

You can generate all the data with a single command:

```bash
$ ./release-2.1.sh all
```

If `config.bash` is correctly configured, this command will produce
all the data. It will take some time, however (e.g., 6 hours or more).

## Parallelized Execution

If you have [HTCondor](http://research.cs.wisc.edu/htcondor/)
installed, you can make use of the provided DAGMAN script to
parallelize some of the intesive tasks. It divides the following tasks
into 10 separate jobs:

- `prepare-txt` (assigning IGT IDs to the text instances)
- `prepare-xigt` (importing the data into the Xigt format, cleaning,
   and normalizing)
- `enriche-xigt` (enriching the Xigt data with INTENT)

However, it cannot parallelize the following tasks, as they require
the whole data sets in order to run:

- `txt-split` (split text instances by language)
- `xigt-split` (split Xigt instances by language)
- `enrich-split` (split enriched Xigt instances by language)
- `lang-summary` (count instances by language)
- `doc-summary` (count structures in instances)
- `compress` (produce `.tbz2` archives of the data)

Because some of the unparallelizable tasks are also intensive,
execution will still take several hours, but it should be faster than
the single-thread execution.

