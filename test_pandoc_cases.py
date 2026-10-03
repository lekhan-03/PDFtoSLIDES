import pypandoc
import zipfile
import tempfile
import uuid
from pathlib import Path
from lxml import etree

text = "Formula: $\\begin{cases} x & \\text{if } y \\\\ 0 & \\text{otherwise} \\end{cases}$"
tmp_path = Path(tempfile.gettempdir()) / f"tmp_{uuid.uuid4().hex}.docx"
pypandoc.convert_text(text, 'docx', format='markdown', outputfile=str(tmp_path))

with zipfile.ZipFile(tmp_path) as z:
    xml_data = z.read('word/document.xml')

root = etree.fromstring(xml_data)
m_ns = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
omaths = root.xpath('.//m:oMath', namespaces=m_ns)
for o in omaths:
    print(etree.tostring(o, pretty_print=True).decode('utf-8'))
