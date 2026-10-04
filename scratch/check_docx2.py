import zipfile

with zipfile.ZipFile('data/tests/Integrals_PU_board_Questions.docx', 'r') as z:
    xml_content = z.read('word/document.xml').decode('utf-8')

idx = xml_content.find('Statement 1 is true, and Statement 2 is true, Statement 2 is correct explanation for Statement')
if idx != -1:
    snippet = xml_content[idx:idx+1000]
    print(snippet)
