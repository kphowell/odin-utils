
# common operations for odinclean and odinnormalize

import re

from xigt import Item

PRITAGS = ('L','G','T','L-G','L-T','G-T','L-G-T','M','B','C')
SECTAGS = ('AC','AL','CN','CR','DB','EX','LN','LT','SY')

def copy_items(items):
    return [
        Item(id=item.id, type=item.type,
             attributes=item.attributes, text=item.text)
        for item in items
    ]

def get_tags(item):
    return item.attributes.get('tag', '').split('+')

def remove_blank_items(items):
    return [
        i for i in items
        if (i.text or '').strip() != ''
    ]

def min_indent(items, tags=None):
    # find the minimum indentation among items
    if tags is None: tags = PRITAGS
    tags = set(tags).difference(['M','B'])
    indents = []
    for item in items:
        tag = get_tags(item)[0]
        if tag in tags:
            indents.append(re.match(r'\s*', item.text, re.U).end())
    return min(indents or [0])

def shift_left(items, tags=None):
    if tags is None: tags = PRITAGS
    tags = set(tags).difference(['M','B'])
    maxshift = min_indent(items, tags)

    for item in items:
        tag = get_tags(item)[0]
        if tag == 'M':
            item.text = item.text.strip()
        elif tag in tags:
            item.text = item.text[maxshift:]
    return items

