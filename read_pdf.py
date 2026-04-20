import pdfplumber
pdf = pdfplumber.open(r'c:\Users\holvoet\Documents\CV\CV_Marion_Holvoet.pdf')
print('Pages:', len(pdf.pages))
for i, page in enumerate(pdf.pages):
    t = page.extract_text()
    print(f'Page {i+1} text length:', len(t) if t else 0)
    if t:
        print(t)
    else:
        print('NO TEXT')
pdf.close()
