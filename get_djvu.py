#!/usr/bin/env python3
#
# get_djvu.py - Python script for downloading books from Czech National Library
# Copyright (C) 2017 Martin Doucha
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from lxml import etree
from djvu import decode, sexpr
import requests
import time
import sys
import os
import tempfile
import traceback
import subprocess

# XML Namespace map
_nsmap = dict(m='http://www.loc.gov/METS/',
    marc='http://www.loc.gov/MARC21/slim',
    dc='http://purl.org/dc/elements/1.1/',
    odc='http://www.openarchives.org/OAI/2.0/oai_dc/')

# Partial ISO 639-2B to ISO 639-1 language map
# Ancient Greek doesn't have ISO 639-1 code, use Modern Greek 'el' instead
langs = dict(chu='cu', cze='cs', eng='en', fre='fr', ger='de', grc='el',
    heb='he', ita='it', lat='la', pol='pl', rum='ro', rus='ru', scc='sr',
    scr='hr', slo='sk', slv='sl', swe='sv', ukr='uk')
# Special codes representing groups of languages, no ISO 639-1 codes
lang_grp = dict(mul='(Multiple unspecified languages)',
    sla='(Slavic languages)', wen='(Sorbian languages)')

def merge_djvu(outfile, pagelist):
    # djvm -c outfile page1 page2 ...
    # Change the next line if you use some other DJVU merge program
    ret = subprocess.run(['djvm', '-c', outfile] + pagelist)
    if ret.returncode != 0:
        raise ChildProcessError('Failed to merge pages into single DJVU file')

def set_djvu_text(ctx, filename, text):
    doc = ctx.new_document(decode.FileUri(filename))
    doc.decoding_job.wait()
    page = doc.pages[0]
    w, h = page.width, page.height
    data = sexpr.Expression([sexpr.Symbol('page'), 0, 0, w-1, h-1, text])
    script = 'select 1; set-txt; ' + data.as_string()
    ret = subprocess.run(['djvused', '-s', '-e', script, filename])
    if ret.returncode != 0:
        raise ChildProcessError('Failed to create DJVU text layer')

def _single_node(node, xpath):
    ret = node.xpath(xpath, namespaces=_nsmap)
    if len(ret) != 1:
        err = 'XPath query returned unexpected number of results: {0}'
        raise RuntimeError(err.format(len(ret)))
    return ret[0]

def clear_temp(tempdir):
    for filename in os.listdir(tempdir):
        os.unlink(os.path.join(tempdir, filename))

# Parse MARCXML into dict of subfield lists
def parse_marc(recnode):
    ret = dict()
    nodelist = recnode.xpath('marc:datafield', namespaces=_nsmap)
    for node in nodelist:
        tag = node.attrib['tag']
        if tag not in ret:
            ret[tag] = []
        tmp = dict()
        for subnode in node.xpath('marc:subfield', namespaces=_nsmap):
            code = subnode.attrib['code']
            if code not in tmp:
                tmp[code] = []
            tmp[code].append(subnode.text)
        ret[tag].append(tmp)
    return ret

# Convert MARC person name tokens into full name
def join_name(parts):
    return ' '.join(parts['a'] + parts.get('b', []) + parts.get('c', []))

# Convert MARC and Dublin Core data into Wikimedia Commons {{Book}} template
def make_description(xml):
    metsnode = _single_node(xml, "/m:mets")
    marcnode = _single_node(xml, "/m:mets/m:dmdSec[@ID='DMD_MARC']/m:mdWrap/m:xmlData/marc:collection/marc:record")
    dcnode = _single_node(xml, "/m:mets/m:dmdSec[@ID='DMD_DC']/m:mdWrap/m:xmlData/odc:dc")
    marc = parse_marc(marcnode)
    author_types = set(['Author', 'Librettist', 'Composer'])
    editor_types = set(['Editor', 'Compiler'])
    name_list = marc.get('100', []) + marc.get('700', [])
    author_list = [join_name(x) for x in name_list
        if author_types & set(x.get('e', []))]
    editor_list = [join_name(x) for x in name_list
        if editor_types & set(x.get('e', []))]
    translator_list = [join_name(x) for x in name_list
        if 'Translator' in x.get('e', [])]
    illust_list = [join_name(x) for x in name_list
        if 'Illustrator' in x.get('e', [])]
    titlefield = dict((x for f in marc['245'] for x in f.items()))
    lang_list = [x.text for x in dcnode.xpath('dc:language',namespaces=_nsmap)]
    ret = []
    if author_list:
        ret.append(('Author', '; '.join(author_list)))
    if translator_list:
        ret.append(('Translator', '; '.join(translator_list)))
    if editor_list:
        ret.append(('Editor', '; '.join(editor_list)))
    if illust_list:
        ret.append(('Illustrator', '; '.join(illust_list)))
    ret.append(('Title', titlefield['a'][0]))
    if 'b' in titlefield:
        ret.append(('Subtitle', titlefield['b'][0]))
    if '440' in marc:
        ret.append(('Series title', ', '.join(marc['440'][0]['a'])))
    if 'n' in titlefield or 'p' in titlefield:
        tmp = titlefield.get('n', []) + titlefield.get('p', [])
        ret.append(('Volume', ': '.join(tmp)))
    if '260' in marc:
        pubfield = marc['260'][0]
        if 'b' in pubfield:
            ret.append(('Publisher', pubfield['b'][0]))
        if 'f' in pubfield:
            ret.append(('Printer', pubfield['f'][0]))
        if 'c' in pubfield:
            ret.append(('Date', pubfield['c'][0]))
        if 'a' in pubfield:
            ret.append(('City', pubfield['a'][0]))
    if len(lang_list) == 1:
        tmp = lang_list[0]
        ret.append(('Language', langs[tmp] if tmp in langs else lang_grp[tmp]))
    elif lang_list:
        tpllist = ['{{language|%s}}' % langs[x] if x in langs else lang_grp[x]
            for x in lang_list]
        ret.append(('Language', ', '.join(tpllist)))
    if '520' in marc:
        ret.append(('Description', marc['520'][0]['a'][0]))
    objid = metsnode.attrib['OBJID']
    ret.append(('Source', '{{Kramerius link|%s|%s}}'%tuple(objid.split('/'))))
    ret.append(('Permission', '{{PD-old}}'))
    ret.append(('Image page', '1'))
    ret.append(('Wikisource', ':s:cs:Index:{{PAGENAME}}'))
    return '{{' + '\n |'.join(['Book'] + [' = '.join(x) for x in ret]) + '\n}}'

def parse_filegroup(groupnode, mimetype):
    href = '{http://www.w3.org/1999/xlink}href'
    xpath = "m:file[@USE='Page' and @MIMETYPE='%s']" % mimetype
    nodelist = groupnode.xpath(xpath, namespaces=_nsmap)
    ret = dict()
    for node in nodelist:
        key = node.attrib['ID']
        ret[key] = _single_node(node, "m:FLocat[@LOCTYPE='URL']").attrib[href]
    return ret

def process_mets(tempdir, filename):
    session = requests.Session()
    ctx = decode.Context()
    outfile = os.path.basename(filename).rsplit('.', 1)[0] + '.djvu'

    # Parse METS file and read list of DJVU page URLs
    xml = etree.parse(filename)
    imgfiles = _single_node(xml, "/m:mets/m:fileSec/m:fileGrp[@USE='img']")
    imgurls = parse_filegroup(imgfiles, 'image/vnd.djvu')
    txtfiles = _single_node(xml, "/m:mets/m:fileSec/m:fileGrp[@USE='txt']")
    txturls = parse_filegroup(txtfiles, 'text/plain')

    # Check that there is something to do
    if not imgurls:
        print('No DJVU pages found in %s' % filename)
        return

    # Zip image and text URLs properly via <mets:structMap> records
    xpath = "/m:mets/m:structMap[@TYPE='Pages']/m:div[@TYPE='Pages']"
    structnode = _single_node(xml, xpath)
    pageurls = []
    for node in structnode.xpath('m:div', namespaces=_nsmap):
        img = txt = None
        for subnode in node.xpath('m:fptr', namespaces=_nsmap):
            key = subnode.attrib['FILEID']
            if key in imgurls:
                img = imgurls[key]
            elif key in txturls:
                txt = txturls[key]
        # Text URLs are optional, some books don't have them at all
        if not img:
            msg = '%s: No image URL for page %s'
            raise RuntimeError(msg % (filename, node.attrib['ORDER']))
        pageurls.append((img, txt))

    pagelist = []
    description = make_description(xml)

    # Download individual pages
    for pagenum, (img, txt) in enumerate(pageurls, 1):
        pagefile = os.path.join(tempdir, 'page-%04d.djvu' % pagenum)
        response = session.get(img, stream=True)
        response.raise_for_status()
        with open(pagefile, 'wb') as fw:
            fw.write(response.raw.read())
        if txt:
            response = session.get(txt)
            response.raise_for_status()
            # Response has no encoding, requests incorrectly assumes ISO-8859-1
            response.encoding = 'utf-8'
            set_djvu_text(ctx, pagefile, response.text.replace('\r', ''))
        pagelist.append(pagefile)
        time.sleep(1)

    # Merge pages into single DJVU file
    merge_djvu(outfile, pagelist)
    print(outfile)
    print(description)
    print()

if __name__ == '__main__':
    tempdir = tempfile.mkdtemp()
    try:
        for filename in sys.argv[1:]:
            process_mets(tempdir, filename)
            clear_temp(tempdir)
    except:
        traceback.print_exc()
        pass
    clear_temp(tempdir)
    os.rmdir(tempdir)
