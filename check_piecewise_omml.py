import zipfile
from lxml import etree

with zipfile.ZipFile("Integrals_output3.pptx") as z:
    slides_with_piecewise = []
    for name in z.namelist():
        if name.startswith("ppt/slides/slide"):
            xml_data = z.read(name)
            root = etree.fromstring(xml_data)
            m_ns = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
            
            # Check for m:d that has a "{" begChr
            d_elements = root.xpath(".//m:d", namespaces=m_ns)
            for d in d_elements:
                begChr = d.xpath(".//m:begChr/@m:val", namespaces=m_ns)
                if begChr and begChr[0] == "{":
                    # ensure it contains m:m (matrix) or m:eqArr
                    if d.xpath(".//m:m", namespaces=m_ns) or d.xpath(".//m:eqArr", namespaces=m_ns):
                        slides_with_piecewise.append(name)
                        break
                        
    print(f"Found {len(slides_with_piecewise)} slides with piecewise functions")
    for s in slides_with_piecewise:
        print(f" - {s}")
