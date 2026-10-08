import zipfile, lxml.etree as E, posixpath
z=zipfile.ZipFile('SolutionNEET_safe.pptx')
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
for f in ['ppt/slides/slide1.xml','ppt/slides/slide2.xml','ppt/slides/slide4.xml','ppt/slides/slide5.xml']:
    root=E.fromstring(z.read(f))
    print(f, ' | '.join(root.xpath('.//a:t/text()',namespaces=ns))[:1000])
slides=[n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
blank=[n for n in slides if not ''.join(E.fromstring(z.read(n)).xpath('.//a:t/text()',namespaces=ns)).strip()]
print('blank_slides',blank)
missing=[]
for n in slides[1:]:
    text=''.join(E.fromstring(z.read(n)).xpath('.//a:t/text()',namespaces=ns))
    if not all(f'{l}.' in text for l in 'ABCD'):
        # Options may wrap without labels in source; leave detailed list for inspection.
        missing.append(n)
print('slides_missing_one_or_more_option_labels',missing)
# Validate all internal relationship targets.
parts=set(z.namelist())
bad=[]
for n in [x for x in parts if x.endswith('.rels')]:
    rel_root=E.fromstring(z.read(n))
    source=n.replace('\\','/').replace('/_rels/','/').removesuffix('.rels') if '/_rels/' in n else ''
    base=posixpath.dirname(source)
    for rel in rel_root.xpath('//*[local-name()="Relationship"]'):
        if rel.get('TargetMode')=='External': continue
        target=posixpath.normpath(posixpath.join(base,rel.get('Target')))
        if target not in parts: bad.append((n,target))
print('orphan_relationship_targets',bad[:15], 'count',len(bad))
