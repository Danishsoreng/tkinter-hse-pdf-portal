# tkinter-hse-pdf-portal
A Tkinter-based PDF report viewer and e-signature portal for HSE reports

# HSE Report Portal - Tkinter PDF Viewer & E-Signer

This project is a Python-based GUI portal to load HSE report PDFs, view them, and apply officer e-signatures manually or automatically.

## Features

- PDF rendering with zoom, scroll, and drag
- E-signature placement via dropdown roles
- Integration with MySQL for officer data and signature images
- Saves PDF with applied signatures using PyPDF2 + reportlab
- Note : Signs Fetch From local Database (Mysql)

## Requirements

- Python 3.8+
- PyMuPDF (`pip install pymupdf`)
- Pillow
- mysql-connector-python
- PyPDF2==2.12.1
- reportlab
- ui/ux figma
- figma design to tkinter design
## How to Run

```bash
python portal.py
