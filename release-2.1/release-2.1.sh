#!/bin/bash

# usage: release-2.1.sh [OPTIONS] COMMAND [COMMAND..] (see usage() below)
# see config.bash for setting up for your local environment

usage() {
cat << EOF
usage: release-2.1.sh [OPTIONS] COMMAND [COMMAND..]
  COMMANDs:
    all          : run all commands on all data
    txt          : prepare text directories
    xigt         : prepare xigt directories
    enrich       : prepare xigt-enriched directories
    txt-split    : create language splits for txt files
    xigt-split   : create language splits for xigt files
    enrich-split : create langauge splits for enriched xigt files
    lang-summary : generate summary of languages
    doc-summary  : generate summary of document contents
    compress     : create tbz2 archives

  OPTIONs:
    --range A:B  : run from file #A to #B (omit A/B to do all up-to-B/from-A;
                   txt|xigt|enrich commands only)

  EXAMPLES:
    release-2.1.sh all
    release-2.1.sh --range 1:10000 txt xigt enrich
    release-2.1.sh --range 10001: txt
    release-2.1.sh lang-summary doc-summary compress
EOF
    exit $1
}


[ $# -ge 1 ] || usage

SCRIPTDIR=$( cd `dirname $0` && pwd)
ODINUTILS=$( cd "$SCRIPTDIR/.." && pwd)
export PYTHONPATH="$ODINUTILS":"$PYTHONPATH"
source "$SCRIPTDIR/config.bash"

# Commands

# default options
declare -A CMD
START=''
END=''
NORANGE=''

while [ $# -ge 1 ]; do
    case "$1" in
        all)
            CMD[txt]=1;
            CMD[xigt]=1
            CMD[enrich]=1
            CMD[txt-split]=1
            CMD[xigt-split]=1
            CMD[enrich-split]=1
            CMD[lang-summary]=1
            CMD[doc-summary]=1
            CMD[compress]=1
            CMD[epilogue]=1
            NORANGE=true
            ;;
        txt|xigt|enrich)
            CMD[$1]=1
            ;;
        txt-split|xigt-split|enrich-split|lang-summary|doc-summary|compress)
            CMD[$1]=1
            NORANGE=true
            ;;
        --range)
            [ $# -ge 2 ] || usage 1
            [[ "$2" =~ ^[0-9]*:[0-9]*$ ]] || usage 1
            START=`echo "$2" | sed 's/:.*//'`
            END=`echo "$2" | sed 's/[^:]*://'`
            shift
            ;;
        -h|--help) usage 0 ;;
        *) usage 1 ;;
    esac
    shift
done

if [ "$NORANGE" ]; then
    if [ -n "$START" ] || [ -n "$END" ]; then
        echo "--range cannot be used except with the txt, xigt, or enrich commands"
        usage 1
    fi
fi

## Helper functions

check-dir() {
    if [ ! -e "$1" ]; then
        echo "Directory $1 not found; aborting."
        exit 1
    fi
}

make-dir() {
    if [ ! -e "$1" ] && [ `mkdir $2 "$1"` ]; then
        echo "Cannot create directory $1; aborting."
        exit 1
    fi
}

get-files() {
    fs=`find $TXTDIR -name \*.txt | sort -V`
    [ -n "$END" ] && fs=`echo "$fs" | head -n"$END"`
    [ -n "$START" ] && fs=`echo "$fs" | tail -n"+$START"`
    for f in ${fs[@]}; do
        f=`basename "${f%.*}.$2"`
        [ -e "$1/$f" ] || echo "Input file not found: $1/$f" >&2
        echo "$1/$f"
    done
}

## Prepare directories

DATADIR="$RELEASEDIR"/data
BYDOCID="$DATADIR"/by-doc-id
BYLANG="$DATADIR"/by-lang


make-dir "$RELEASEDIR"
make-dir "$DATADIR"
make-dir "$BYDOCID"
make-dir "$BYLANG"

##
## Task functions
##

prepare-txt() {
    check-dir "$TXTDIR"
    make-dir "$BYDOCID/txt" -p
    echo "Creating `basename \"$BYDOCID/txt\"`"
    $PYTHON "$ODINUTILS/odintxt.py" $DBG --assign-igt-ids "$BYDOCID/txt" `get-files "$TXTDIR" txt`
}

prepare-xigt() {
    check-dir "$BYDOCID/txt"
    make-dir "$BYDOCID/xigt" -p
    echo "Creating `basename $BYDOCID`/xigt"
    for f in `get-files "$BYDOCID/txt" txt`; do
        x="$BYDOCID/xigt/"`basename "${f%.txt}"`.xml
        echo -n "  `basename $x` :import"
        $XIGT import \
            $DBG \
            --format odin \
            --config "$SCRIPTDIR/odin-2.1.json" \
            --input "$f" \
            --output "$x"
        echo -n " :clean"
        $PYTHON "$ODINUTILS/odinclean.py" $DBG "$x"
        echo " :normalize"
        $PYTHON "$ODINUTILS/odinnormalize.py" $DBG "$x"
    done
}

enrich-xigt() {
    check-dir "$BYDOCID/xigt"
    make-dir "$BYDOCID/xigt-enriched" -p  # xigt 1.1 aborts if it exists
    echo "Creating `basename $BYDOCID`/xigt-enriched"
    echo " (enriching `basename $BYDOCID`/xigt with INTENT)"
    for f in `get-files "$BYDOCID/xigt" xml`; do
        fn="$BYDOCID/xigt-enriched/`basename $f`"
        echo -n "  `basename $fn` :enrich"
        $INTENT enrich \
            --align heur \
            --pos class \
            --parse trans,proj \
            "$f" "$fn"
            # leaving off the following option because of a bug:
            # https://github.com/rgeorgi/intent/issues/1
            #--max-parse-length=25 \
        echo " :sort"
        $XIGT sort \
            $DBG \
            --in-place \
            --tier-deps="segmentation,alignment,dep,head,children,source,target,content" \
            "$fn"
    done
}

txt-split() {
    check-dir "$BYDOCID/txt"
    make-dir "$BYLANG/txt" -p
    echo "Creating `basename \"$BYLANG/txt\"`"
    $PYTHON "$ODINUTILS/odintxt.py" $DBG --split-by=iso-639-3 "$BYLANG/txt" "$BYDOCID/txt"/*.txt
}

split-xigt-files() {
    check-dir "$1"
    # make-dir "$2" -p  # xigt 1.1 aborts if it exists
    echo "Creating `basename $BYLANG`/`basename $2`"
    $XIGT partition $DBG --key-path="$LANGPATH" "$2" "$1"/*.xml
    echo "Sorting IGTs within by-lang corpora by doc-id"
    for f in "$2"/*.xml; do
        $XIGT sort \
            $DBG \
            --in-place \
            --igt-key='@id' \
            "$f"
    done
}

xigt-split() { split-xigt-files "$BYDOCID/xigt" "$BYLANG/xigt"; }
enrich-split() { split-xigt-files "$BYDOCID/xigt-enriched" "$BYLANG/xigt-enriched"; }

language-summaries() {
    for dir in "$BYDOCID" "$BYLANG"; do
        if [ -d "$dir/xigt" ]; then
            echo "Generating language summary for `basename \"$dir\"`"
            $XIGT query \
                --basename \
                --tally 'igt' 'metadata//dc:subject/(@olac:code | text())' \
                --description '{match[1]} ({match[0]})' \
                "$dir/xigt"/*.xml > "$dir/languages.txt"
        fi
    done
}

doc-summaries() {
    for dir in "$BYDOCID/xigt" "$BYLANG/xigt" "$BYDOCID/xigt-enriched" "$BYLANG/xigt-enriched"; do
        if [ -d "$dir" ]; then
            echo "Generating document summaries for `basename \"$dir\"`"
            $XIGT query \
                --basename \
                --count 'igt' --description 'IGTs' \
                --unique 'igt/@doc-id' --description 'source documents' \
                --unique 'igt/metadata//dc:subject/text()' --description 'languages (by name)' \
                --unique 'igt/metadata//dc:subject/@olac:code' --description 'languages (by ISO-693-3 language code)' \
                --tally 'igt' 'tier/@type' --description 'IGTs with tiers: {match!s}' \
                --tally '//tier' '@type' --description 'tiers of type: {match}' \
                "$dir"/*.xml > "$dir/summary.txt"
        fi
    done
}

compress() {
    for dir in "$BYDOCID" "$BYLANG"; do
        pushd "$dir" >/dev/null
        for subdir in "txt" "xigt" "xigt-enriched"; do
            if [ -d "$subdir" ]; then
                echo "Compressing `basename \"$dir\"`/$subdir"
                tar cjf "$subdir".tbz2 "$subdir"
            fi
        done
        popd >/dev/null
    done
}

epilogue() {
    echo "Created the following corpora:"
    pushd "$RELEASEDIR" >/dev/null
    dirs=`find . -type d -print | sed 's/\.\/data\//  /' | grep -v "^\..*$"`
    popd >/dev/null
    echo "$dirs"
    cat << FINALMSG
Now update and place the following files under $RELEASEDIR:
  README.txt               - description of the ODIN corpus
  CHANGELOG.txt            - updates by version
  citations.txt            - mapping of doc-id to document citation
  enrichment_flowchart.pdf - diagram showing the enrichment process
  schema/                  - the RelaxNG schema files for ODIN data
FINALMSG
}

##
## Run commands
##

[ ${CMD[txt]} ] && prepare-txt
[ ${CMD[xigt]} ] && prepare-xigt
[ ${CMD[enrich]} ] && enrich-xigt
[ ${CMD[txt-split]} ] && txt-split
[ ${CMD[xigt-split]} ] && xigt-split
[ ${CMD[enrich-split]} ] && enrich-split
[ ${CMD[lang-summary]} ] && language-summaries
[ ${CMD[doc-summary]} ] && doc-summaries
[ ${CMD[compress]} ] && compress
[ ${CMD[epilogue]} ] && epilogue

exit 0  # if nothing follows the test above and it fails, the script returns 1

