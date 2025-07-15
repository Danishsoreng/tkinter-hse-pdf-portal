# 🛡️ HSE Report Portal (Tkinter PDF Viewer & E-Signer)

This is a complete desktop application built in Python using Tkinter. It is designed to load HSE report PDFs, allow officers to digitally sign them, and save the signed reports. It connects with a MySQL database to fetch officer information and e-signature images.

---

## 📚 Features

- 📄 PDF viewing with zoom, pan, and canvas rendering
- ✍️ Manual and automatic placement of officer e-signatures
- 🧑 Dropdown menus populated from MySQL
- 🗓️ Automatic report date extraction from PDF filename
- 💾 Save edited PDFs with embedded signatures

---

## 🔧 Libraries Used

| Library                 | Purpose                                                                 |
|-------------------------|-------------------------------------------------------------------------|
| `tkinter`               | Python GUI framework                                                    |
| `Pillow` (PIL)          | Image processing (e.g., resizing e-signatures, logos)                   |
| `mysql-connector-python`| MySQL connectivity to fetch officer data and e-signs                    |
| `fitz` (PyMuPDF)        | Load and render PDF files to images                                     |
| `PyPDF2`                | Edit and save PDF files with added content                              |
| `reportlab`             | Create temporary PDF pages with image signatures                        |
| `io`, `re`, `datetime`, `pathlib` | Built-in Python libraries for I/O, regex, date, and path handling |

---

## 🧱 GUI Layout Overview

The app interface is built with multiple `Frame`s in Tkinter:

| Frame Name             | Description                                                               |
|------------------------|---------------------------------------------------------------------------|
| `top_bar_frame`        | Header area with logo, animated title, and report date                    |
| `main_content_frame`   | Divides UI into left (PDF view) and right (controls)                      |
| `frame_pdf`            | Renders the PDF using canvas                                              |
| `controls_frame`       | Contains dropdowns, buttons, and error box                                |

The PDF page is rendered on a `Canvas` widget, where signatures are previewed and placed.

---

## 🚀 Functional Breakdown

### 📄 PDF Loading & Rendering

- Uses `fitz` (PyMuPDF) to open the PDF and convert pages into images
- Automatically zooms to fit the canvas dimensions
- Displays first page on load

```python
pix = page.get_pixmap(matrix=mat)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
canvas.create_image(0, 0, anchor="nw", image=ImageTk.PhotoImage(img))

## How to Run

```bash
python portal.py
