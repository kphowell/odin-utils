#!/bin/bash

# usage: release-2.1.sh TXT-DIR RELEASE-DIR
#  e.g. release-2.1.sh ~/odin/txt/ ~/odin-2.1/

# configure the XIGT variable as necessary
XIGT=xigt  # installed
#XIGT=xigt.sh  # accessible on PATH
#XIGT=/home/../xigt/xigt.sh  # full path
INTENT=intent.py  # accessible on path
#INTENT=/home/.../intent.py  # full path
LANGPATH='metadata//dc:subject/@olac:code'  # XigtPath to language metadata
DOCIDPATH='@doc-id'

DBG='-v'

if [ "$#" -ne 2 ]; then
    echo "usage: release-2.1.sh TXT-DIR RELEASE-DIR"
    exit 1
fi

TXTDIR="$1"
RELEASEDIR="$2"
DATADIR="$RELEASEDIR"/data
TXTBYDOCIDDIR="$DATADIR"/txt-by-doc-id
TXTBYLANGDIR="$DATADIR"/txt-by-lang
BYDOCIDDIR="$DATADIR"/by-doc-id
BYLANGDIR="$DATADIR"/by-lang
BYDOCIDENRICHEDDIR="$DATADIR"/by-doc-id-enriched
BYLANGENRICHEDDIR="$DATADIR"/by-lang-enriched

version_ok() {
   ver1="$1"; ver2="$2"
   vers=`echo -e "$ver1\n$ver2" | sort -V` # sort -V sorts by versions
   highver=`echo "$vers" | tail -n1`
   [ "$ver1" == "$highver" ]
 }

# should we force version 1.1 or allow any 1.1+?
XIGTVERSION=`python -c 'import xigt; print(getattr(xigt, "__version__", "1.0.0"))'`
if [ "$?" -ne 0 ]; then
    echo "The Xigt package is not importable."
    echo "  see: http://depts.washington.edu/uwcl/xigt"
    echo "  try: pip install xigt"
    echo "Aborting."
    exit 1
fi
if [ `version_ok "$XIGTVERSION" "1.1.0"` ]; then
    echo "The Xigt package is version \"$XIGTVERSION\", but it must be >= 1.1.0."
    echo "Try updating your Xigt package."
    echo "Aborting."
    exit 1
fi

if [ ! -e "$TXTDIR" ]; then
    echo "Text directory $TXTDIR not found; aborting."
    exit 1
fi
if [ -e "$RELEASEDIR" ]; then
    echo "Release directory $RELEASEDIR already exists; aborting."
    exit 1
fi
if [ `mkdir "$RELEASEDIR"` ]; then
    echo "Cannot create release directory $RELEASEDIR; aborting."
    exit 1
fi
if [ `mkdir "$DATADIR"` ]; then
    echo "Cannot create data directory $DATADIR; aborting."
    exit 1
fi

##
## TXT DOC SPLITS
##

echo "Creating `basename \"$TXTBYDOCIDDIR\"`"
./odintxt.py $DBG --assign-igt-ids "$TXTBYDOCIDDIR" "$TXTDIR"/*.txt

echo "Creating `basename \"$TXTBYLANGDIR\"`"
./odintxt.py $DBG --split-by=iso-639-3 "$TXTBYLANGDIR" "$TXTBYDOCIDDIR"/*.txt

##
## INITIAL XIGT IMPORT, CLEAN, NORMALIZE, SPLIT
##

echo "Creating `basename \"$BYDOCIDDIR\"`"
$XIGT import \
  $DBG \
  --format odin \
  --config odin-2.1.json \
  --input "$TXTBYDOCIDDIR" \
  --output "$BYDOCIDDIR"

echo "Cleaning `basename \"$TXTBYDOCIDDIR\"`"
./odinclean.py $DBG "$BYDOCIDDIR"/*.xml
echo "Normalizing `basename \"$TXTBYDOCIDDIR\"`"
./odinnormalize.py $DBG "$BYDOCIDDIR"/*.xml

echo "Creating `basename \"$BYLANGDIR\"`"
$XIGT partition $DBG --key-path="$LANGPATH" "$BYLANGDIR" "$BYDOCIDDIR"/*.xml
echo "Sorting IGTs within by-lang corpora by doc-id"
for f in "$BYLANGDIR"/*.xml; do
    $XIGT sort $DBG --in-place --igt-key='@id' "$f"
done

##
## INTENT ENRICHMENT
##

cat << INTENTMSG
Now INTENT should be run to enrich the data. Choose an option:
 (1) Attempt to run INTENT locally
 (2) Run INTENT separately and place the result in the release directory
 (3) Skip enrichment step
INTENTMSG
INTENTOPT=""
while true; do
    case $INTENTOPT in
        1|2|3) break ;;
        *) read -p "Use option [1/2/3]: " INTENTOPT ;;
    esac
done

case $INTENTOPT in
    1)
        echo "Creating `basename \"$BYDOCIDENRICHEDDIR\"`"
        mkdir "$BYDOCIDENRICHEDDIR"
        echo " (enriching `basename \"$BYDOCIDDIR\"` with INTENT)"
        for f in "$BYDOCIDDIR"/*.xml; do
            fn="$BYDOCIDENRICHEDDIR/`basename $f`"
            $INTENT enrich --align heur --pos class --parse trans,proj "$f" "$fn"
        done
        ;;
    2)
        echo "Please run INTENT to enrich each file in $BYDOCIDDIR and output the result to $BYDOCIDENRICHEDDIR."
        echo "  e.g. intent.py enrich --align heur --pos class --parse trans,proj INFILE OUTFILE"
        read -p "When done, press [Enter] to continue..."
        ;;
    3|*)
        echo "Skipping enrichment step."
        ;;
esac

if [ $INTENTOPT -ne 3 ]; then
    echo "Creating `basename \"$BYLANGENRICHEDDIR\"`"
    echo " (grouping `basename \"$BYDOCIDENRICHEDDIR\"` enriched IGTs by language)"
    $XIGT partition $DBG --key-path="$LANGPATH" "$BYLANGENRICHEDDIR" "$BYDOCIDENRICHEDDIR"/*.xml
    echo "Sorting IGTs within by-lang corpora by doc-id"
    for f in "$BYLANGENRICHEDDIR"/*.xml; do
        $XIGT sort $DBG --in-place --igt-key='@id' "$f"
    done
fi

##
## SUMMARIES
##

summarize() {
    dir="$1"
    $XIGT query \
        --basename \
        --unique 'igt' --description 'IGTs' \
        --unique 'igt/@doc-id' --description 'source documents' \
        --unique 'igt/metadata//dc:subject/text()' --description 'languages (by name)' \
        --unique 'igt/metadata//dc:subject/@olac:code' --description 'languages (by ISO-693-3 language code)' \
        --tally 'igt' 'tier/@type' --description 'IGTs with tiers: {match!s}' \
        --tally '//tier' '@type' --description 'tiers of type: {match}' \
        "$dir"/*.xml > "$dir"/summary.txt
}

languages() {
    dir="$1"
    $XIGT query \
        --basename \
        --tally 'igt' 'metadata//dc:subject/(@olac:code | text())' \
        --description '{match[1]} ({match[0]})' \
        "$dir"/*.xml > "$dir"/languages.txt
}

for dir in "$BYDOCIDDIR" "$BYLANGDIR" "$BYDOCIDENRICHEDDIR" "$BYLANGENRICHEDDIR"; do
    if [ -d "$dir" ]; then
        echo "Generating summaries for `basename \"$dir\"`"
        summarize "$dir"
        languages "$dir"
    fi
done

# compress

for dir in "$TXTBYDOCIDDIR" "$TXTBYLANGDIR" "$BYDOCIDDIR" "$BYLANGDIR" "$BYDOCIDENRICHEDDIR" "$BYLANGENRICHEDDIR"; do
    if [ -d "$dir" ]; then
        echo "Compressing `basename \"$dir\"`"
        # realpath will strip trailing / if it exists
        tar cjf "`realpath \"$dir\"`".tbz2 -C "$DATADIR" "`basename \"$dir\"`"
    fi
done

echo "Created the following corpora:"
pushd "$RELEASEDIR" >/dev/null
dirs=`find . -type d -print | sed 's/\.\/data\//  /' | grep -v "^\..*$"`
popd >/dev/null
echo "$dirs"
cat << FINALMSG
Now update and place the following files under $RELEASEDIR:
  README.txt    - description of the ODIN corpus
  CHANGELOG.txt - updates by version
  citations.txt - mapping of doc-id to document citation
FINALMSG

