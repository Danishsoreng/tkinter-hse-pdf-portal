import io
import re
from pathlib import Path
from datetime import datetime
from tkinter import (
    Tk, Canvas, Text, Button, Label, Frame, Scrollbar, messagebox, END, filedialog,
    VERTICAL, RIGHT, Y, LEFT, BOTH
)
from tkinter.ttk import Combobox
from PIL import Image, ImageTk
import mysql.connector
import fitz  # PyMuPDF

# Define the path for assets. Please update this path
# to the correct directory where your 'image_1.png' (IndianOil logo) is located.
# Example: ASSETS_PATH = Path("C:/Your/Path/To/Assets")
OUTPUT_PATH = Path(__file__).parent
ASSETS_PATH = OUTPUT_PATH / Path(r"C:\DataAnalysis\Projects\pdfreader\TkinterConverison\build\assets\frame0")

class HSEReportPortalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HSE Report Portal")
        # Reduced window height from 780 to 760 to prevent bottom border cutoff
        self.root.geometry("1160x760") 
        self.root.configure(bg="#E0E0E0")
        self.root.resizable(True, True)

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        ###
        # Variables
        ###
        self.pdf_path = None
        self.pdf_img_tk = None
        self.pdf_doc = None
        self.current_zoom = 1.0
        self.current_page_num = 0
        self.signature_position_pdf = None # (x,y) in PDF points (bottom-left origin) for the clicked TOP-LEFT of signature

        # E-sign coordinates (X from left, Y from BOTTOM in PDF points)
        self.esign_coordinates = {
            "Initiated By": (81.6, 123.7),
            "Verified By": (176.0, 121.3),
            "Checked By 1": (272.0, 118.1),
            "Checked By 2": (368.8, 119.7),
            "Checked By 3": (462.4, 121.3),
            "Reviewed By Officer 1": (105.6, 38.1),
            "Reviewed By Officer 2": (240.8, 37.3),
            "Approved By": (408.0, 44.5)
        }

        # Stores {role_title: selected_name} for automated placement when "LOAD SIGNATURE" is clicked
        self.selected_officer_assignments = {} 

        # Cache for loaded signatures: {name: {'pil_img': PIL_Image, 'tk_img': ImageTk.PhotoImage, 'image_bytes': bytes}}
        self.loaded_signatures_cache = {}
        
        # Data for the currently active signature (the one selected in dropdown for manual placement)
        self.current_active_signature_data = {
            'pil_img': None,
            'tk_img': None, # This will be the PhotoImage for the top-right preview
            'name': None,
            'image_bytes': None # Store original bytes for apply_signature
        }

        self.temp_scaled_sig_tk = None # Temporary PhotoImage for the click-placement preview

        # Stores signatures placed on the PDF canvas, pending final application on save
        # Structure: {page_number: [{'pil_img': PIL_Image, 'position': (x,y), 'height_pt': float, 'name': str}, ...]}
        self.placed_signatures = {}

        # Variables for animated logo
        self.logo_frames = []
        self.logo_frame_index = 0
        self.logo_animation_id = None # To store the after() ID for canceling animation
        self.animation_speed_ms = 100 # Milliseconds between frames (adjust as needed)

        # Variables for HSE Report Portal heading animation
        self.hse_label_colors = []
        self.hse_label_color_index = 0
        self.hse_label_animation_direction = 1 # 1 for fade in (black to white), -1 for fade out (white to black)
        self.hse_label_animation_id = None
        self.num_color_steps = 30 # Number of steps for the fade
        self.fade_speed_ms_heading = 50 # Speed of fade animation for heading (ms per step)

        # List of officer role dropdowns
        self.officer_roles_config = [
            "Initiated By", "Verified By", "Checked By 1", "Checked By 2",
            "Checked By 3", "Reviewed By Officer 1", "Reviewed By Officer 2", "Approved By"
        ]
        self.officer_dropdowns = {} # Stores references to the Combobox widgets by role title

        ###
        # Build UI
        ###
        self.build_ui()
        self.fetch_names()
        self._generate_hse_label_colors() # Generate colors once
        self._animate_hse_label() # Start the text animation

    def create_rounded_button(self, parent, text, command, bg_color, fg_color="black", font=("Inter", 10, "bold"), pady_val=8, padx_val=15):
        """Helper to create a button with common styling and hover effects."""
        button = Button(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            font=font,
            relief="raised",
            bd=2,
            padx=padx_val,
            pady=pady_val,
            activebackground=self._darken_color(bg_color, 10), # Darken on click
            activeforeground=fg_color
        )
        # Bind hover effects
        button.bind("<Enter>", lambda e, b=button, c=bg_color: self._on_button_enter(b, c))
        button.bind("<Leave>", lambda e, b=button, c=bg_color: self._on_button_leave(b, c))
        return button

    def _darken_color(self, hex_color, percent):
        """Darkens a hex color by a given percentage."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        darkened_rgb = tuple(max(0, int(c * (1 - percent / 100))) for c in rgb)
        return '#%02x%02x%02x' % darkened_rgb

    def _lighten_color(self, hex_color, percent):
        """Lightens a hex color by a given percentage."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        lightened_rgb = tuple(min(255, int(c * (1 + percent / 100))) for c in rgb)
        return '#%02x%02x%02x' % lightened_rgb

    def _on_button_enter(self, button, original_bg_color):
        """Changes button color on mouse enter."""
        # Use a slightly lighter version for hover, or a distinct hover color
        button.config(bg=self._lighten_color(original_bg_color, 15)) 

    def _on_button_leave(self, button, original_bg_color):
        """Restores button color on mouse leave."""
        button.config(bg=original_bg_color)

    # New helper function for color interpolation
    def _interpolate_color(self, color1_hex, color2_hex, steps, current_step):
        """Interpolates between two hex colors to get an intermediate color."""
        r1, g1, b1 = tuple(int(color1_hex[i:i+2], 16) for i in (1, 3, 5))
        r2, g2, b2 = tuple(int(color2_hex[i:i+2], 16) for i in (1, 3, 5))

        if steps <= 1: return color2_hex # Avoid division by zero or single step

        ratio = current_step / (steps - 1)
        
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)

        return f'#{r:02x}{g:02x}{b:02x}'

    def _generate_hse_label_colors(self):
        """Generates the list of colors for the HSE label animation."""
        self.hse_label_colors = []
        # Fade from black to white
        for i in range(self.num_color_steps):
            self.hse_label_colors.append(self._interpolate_color("#000000", "#FFFFFF", self.num_color_steps, i))
        # Fade from white to black (excluding start/end to avoid duplicates in cycle)
        for i in range(self.num_color_steps - 2, 0, -1): # Start from num_color_steps-2 down to 1
            self.hse_label_colors.append(self._interpolate_color("#000000", "#FFFFFF", self.num_color_steps, i))

    def _animate_hse_label(self):
        """Performs the black and white fade animation for the HSE Report Portal heading."""
        if not self.hse_label_colors:
            return

        # Update the foreground color of the label
        current_color = self.hse_label_colors[self.hse_label_color_index]
        self.hse_label.config(fg=current_color)

        # Move to the next color in the sequence
        self.hse_label_color_index += self.hse_label_animation_direction

        # Reverse direction if we hit the start or end of the color list
        if self.hse_label_color_index >= len(self.hse_label_colors) or self.hse_label_color_index < 0:
            self.hse_label_animation_direction *= -1 # Reverse direction
            # Adjust index to prevent going out of bounds immediately after reversal
            self.hse_label_color_index = max(0, min(len(self.hse_label_colors) - 1, self.hse_label_color_index))
            

        # Schedule the next animation step
        self.hse_label_animation_id = self.root.after(self.fade_speed_ms_heading, self._animate_hse_label)


    def build_ui(self):
        self.top_bar_frame = Frame(self.root, bg="#E0E0E0", bd=2, relief="solid")
        self.top_bar_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.top_bar_frame.grid_columnconfigure(1, weight=1)
        self.top_bar_frame.grid_rowconfigure(0, weight=1)

        # IndianOil Logo Placeholder (with animation attempt)
        try:
            animated_logo_path = ASSETS_PATH / "animated_logo.gif"
            if animated_logo_path.exists():
                gif_img = Image.open(animated_logo_path)
                try:
                    while True:
                        frame = gif_img.copy()
                        frame = frame.resize((150, 56), Image.LANCZOS) # User's requested resize
                        self.logo_frames.append(ImageTk.PhotoImage(frame))
                        gif_img.seek(len(self.logo_frames))
                except EOFError:
                    pass

                if self.logo_frames:
                    # Adjusted padx and pady for custom logo size and border
                    self.logo_label = Label(self.top_bar_frame, image=self.logo_frames[0], bg="#F47D23", relief="solid", borderwidth=1, padx=10, pady=10)
                    self.logo_label.grid(row=0, column=0, padx=(5,0), pady=5, sticky="w")
                    self._animate_logo()
                else:
                    raise ValueError("GIF file has no frames or is corrupted.")
            else:
                raise FileNotFoundError("Animated GIF not found, falling back to static image.")

        except (FileNotFoundError, ValueError, Exception) as e:
            print(f"Logo load error: {e}. Attempting to load static image 'image_1.png'.")
            try:
                static_logo_path = ASSETS_PATH / "image_1.png"
                logo_img = Image.open(static_logo_path).convert("RGBA")
                logo_img = logo_img.resize((56, 56), Image.LANCZOS)
                self.logo_img_tk = ImageTk.PhotoImage(logo_img)
                # Adjusted padx and pady for consistency with custom logo, or you can revert to smaller
                self.logo_label = Label(self.top_bar_frame, image=self.logo_img_tk, bg="#F47D23", relief="solid", borderwidth=1, padx=10, pady=10)
                self.logo_label.image = self.logo_img_tk
                self.logo_label.grid(row=0, column=0, padx=(5,0), pady=5, sticky="w")
            except Exception as e_static:
                print(f"Static logo load error: {e_static}. Displaying text fallback.")
                self.logo_img_tk = None
                # Adjusted padx and pady for consistency
                self.logo_label = Label(self.top_bar_frame, text="IndianOil\n\nभारतीय", font=("Inter", 10, "bold"), fg="white", bg="#F47D23", relief="solid", borderwidth=1, padx=10, pady=10)
                self.logo_label.grid(row=0, column=0, padx=(5,0), pady=5, sticky="w")


        # HSE REPORT PORTAL Label
        self.hse_label = Label(self.top_bar_frame, text="HSE REPORT PORTAL", font=("Inter", 16, "bold"), bg="#E0E0E0")
        self.hse_label.grid(row=0, column=1, padx=20, pady=10, sticky="w")

        # REPORT DATE Label and Entry
        report_date_frame = Frame(self.top_bar_frame, bg="#E0E0E0")
        report_date_frame.grid(row=0, column=2, padx=10, pady=10, sticky="e")
        report_date_label = Label(report_date_frame, text="REPORT DATE :", font=("Inter", 10, "bold"), bg="#E0E0E0")
        report_date_label.pack(side="left", padx=5)
        self.report_date_entry = Text(report_date_frame, width=20, height=1, bd=1, relief="solid", font=("Inter", 10))
        self.report_date_entry.pack(side="right")
        self.report_date_entry.insert(END, "")
        self.report_date_entry.config(state="disabled")

        # Main Content Area Frame (below top bar)
        self.main_content_frame = Frame(self.root, bg="#E0E0E0")
        self.main_content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.main_content_frame.grid_columnconfigure(0, weight=3)
        self.main_content_frame.grid_columnconfigure(1, weight=2)

        # Left Panel (PDF PORTAL)
        self.frame_pdf = Frame(self.main_content_frame, bg="#D3D3D3", bd=2, relief="solid")
        self.frame_pdf.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=(5, 5))
        self.frame_pdf.grid_rowconfigure(0, weight=1)
        self.frame_pdf.grid_columnconfigure(0, weight=1)

        # Canvas for PDF content
        self.canvas_pdf = Canvas(
            self.frame_pdf,
            bg="#ffffff",
            cursor="cross",
            bd=0,
            highlightthickness=0
        )
        self.canvas_pdf.pack(fill="both", expand=True) 

        # Bind mouse events for drag-to-pan
        self.drag_start_x = None
        self.drag_start_y = None
        self.is_dragging = False
        self.drag_threshold = 5 # Pixels to move before considering it a drag vs. a click
        self.canvas_pdf.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas_pdf.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas_pdf.bind("<ButtonRelease-1>", self.on_drag_end)

        # Initial "PDF PORTAL" text on the canvas
        self.canvas_pdf.create_text(
            self.canvas_pdf.winfo_width() / 2, self.canvas_pdf.winfo_height() / 2,
            text="PDF PORTAL", font=("Inter", 18, "bold"), fill="#808080", tags="pdf_portal_text"
        )
        # Only recenter text if no PDF is loaded
        self.canvas_pdf.bind("<Configure>", self._recenter_pdf_portal_text)

        # Right Panel (Controls and Error Box)
        self.controls_frame = Frame(self.main_content_frame, bg="#D3D3D3", bd=2, relief="solid")
        self.controls_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 5), pady=(5, 5))
        
        self.controls_frame.grid_rowconfigure(0, weight=0)
        self.controls_frame.grid_rowconfigure(1, weight=0)
        self.controls_frame.grid_rowconfigure(2, weight=0)
        self.controls_frame.grid_rowconfigure(3, weight=1)
        self.controls_frame.grid_columnconfigure(0, weight=1)

        # View Portal Label
        view_portal_label = Label(self.controls_frame, text="VIEW PORTAL", font=("Inter", 12, "bold"), bg="#D3D3D3")
        view_portal_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        # Container for all officer dropdowns and main buttons
        officer_buttons_frame = Frame(self.controls_frame, bg="#D3D3D3")
        officer_buttons_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        officer_buttons_frame.grid_columnconfigure(0, weight=1) 
        officer_buttons_frame.grid_columnconfigure(1, weight=1)

        dropdown_grid_map = {
            "Initiated By": (0, 0),
            "Verified By": (0, 1),
            "Checked By 1": (2, 0),
            "Checked By 2": (2, 1),
            "Checked By 3": (4, 0),
            "Reviewed By Officer 1": (4, 1),
            "Reviewed By Officer 2": (6, 0),
            "Approved By": (6, 1)
        }

        for role_title in self.officer_roles_config:
            row, col = dropdown_grid_map.get(role_title, (0, 0))

            label = Label(
                officer_buttons_frame,
                text=role_title,
                bg="#D3D3D3",
                fg="#111827",
                font=("Inter", 10, "bold")
            )
            label.grid(row=row, column=col, pady=(2, 0), padx=5, sticky="w")

            dropdown = Combobox(officer_buttons_frame, state="readonly", font=("Inter", 10))
            dropdown.grid(row=row + 1, column=col, pady=(0, 5), padx=5, sticky="ew")
            dropdown.bind("<<ComboboxSelected>>", self._on_officer_dropdown_selected)
            self.officer_dropdowns[role_title] = dropdown

        button_start_row = 8 
        button_pady_common = 3
        
        self.btn_zoom_in = self.create_rounded_button(officer_buttons_frame, "ZOOM IN", self.zoom_in, "#A7C7E7", pady_val=button_pady_common)
        self.btn_zoom_in.grid(row=button_start_row, column=0, columnspan=2, pady=(15, button_pady_common), sticky="ew")
        button_start_row += 1

        self.btn_zoom_out = self.create_rounded_button(officer_buttons_frame, "ZOOM OUT", self.zoom_out, "#A7C7E7", pady_val=button_pady_common)
        self.btn_zoom_out.grid(row=button_start_row, column=0, columnspan=2, pady=button_pady_common, sticky="ew")
        button_start_row += 1

        self.btn_load_sig = self.create_rounded_button(officer_buttons_frame, "LOAD SIGNATURE", self.load_signature, "#A7C7E7", pady_val=button_pady_common)
        self.btn_load_sig.grid(row=button_start_row, column=0, columnspan=2, pady=button_pady_common, sticky="ew")
        button_start_row += 1

        self.btn_load_pdf = self.create_rounded_button(officer_buttons_frame, "LOAD PDF", self.load_pdf, "#A7C7E7", pady_val=button_pady_common)
        self.btn_load_pdf.grid(row=button_start_row, column=0, columnspan=2, pady=button_pady_common, sticky="ew")
        button_start_row += 1

        self.btn_apply_sign = self.create_rounded_button(officer_buttons_frame, "APPLY ESIGN", self.apply_signature, "#90EE90", font=("Inter", 10, "bold"), pady_val=8)
        self.btn_apply_sign.grid(row=button_start_row, column=0, columnspan=2, pady=(15, 5), sticky="ew")
        button_start_row += 1

        self.btn_save_pdf = self.create_rounded_button(officer_buttons_frame, "SAVE PDF", self.save_pdf, "#66BB6A", font=("Inter", 10, "bold"), pady_val=8)
        self.btn_save_pdf.grid(row=button_start_row, column=0, columnspan=2, pady=5, sticky="ew")
        button_start_row += 1

        # Error Box
        error_box_label = Label(self.controls_frame, text="ERROR BOX", font=("Inter", 12, "bold"), bg="#D3D3D3")
        error_box_label.grid(row=2, column=0, padx=10, pady=(20, 5), sticky="w")

        self.error_frame = Frame(self.controls_frame, bg="#fee2e2", bd=1, relief="solid")
        self.error_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.error_text = Text(
            self.error_frame,
            wrap='word',
            bg="#fee2e2",
            fg="#b91c1c",
            state='disabled',
            font=("Segoe UI", 11),
            bd=0
        )
        self.error_text.pack(fill="both", expand=True)

        self.error_scrollbar = Scrollbar(self.error_frame, orient="vertical", command=self.error_text.yview)
        self.error_scrollbar.pack(side="right", fill="y")
        self.error_text.config(yscrollcommand=self.error_scrollbar.set)

    def _animate_logo(self):
        """Cycles through GIF frames for the logo animation."""
        if self.logo_frames:
            self.logo_frame_index = (self.logo_frame_index + 1) % len(self.logo_frames)
            self.logo_label.config(image=self.logo_frames[self.logo_frame_index])
            self.logo_animation_id = self.root.after(self.animation_speed_ms, self._animate_logo)

    def _recenter_pdf_portal_text(self, event):
        # Recenter the "PDF PORTAL" text when the canvas is resized, if no PDF is loaded
        if not self.pdf_doc and self.canvas_pdf.find_withtag("pdf_portal_text"):
            self.canvas_pdf.coords("pdf_portal_text", event.width / 2, event.height / 2)

    def log_error(self, msg):
        self.error_text.configure(state="normal")
        self.error_text.delete(1.0, "end")
        self.error_text.insert("end", msg)
        self.error_text.configure(state="disabled")

    def fetch_names(self):
        try:
            conn = mysql.connector.connect(host="localhost", user="root", password="password", database="project")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM iocl ORDER BY empid ASC")
            result = cursor.fetchall()
            all_names = [row[0] for row in result]
            conn.close()

            name_index = 0

            for role_title in self.officer_roles_config:
                dropdown = self.officer_dropdowns[role_title]
                options_for_dropdown = ["--Please select Name--"]
                
                if name_index < len(all_names):
                    options_for_dropdown.append(all_names[name_index])
                    name_index += 1

                dropdown['values'] = options_for_dropdown
                dropdown.set(options_for_dropdown[0])

        except Exception as e:
            self.log_error(f"DB Error fetching names: {e}")

    def set_report_date_from_filename(self, path):
        filename = Path(path).stem
        m = re.search(r"hse_report[_]?(\d{2})(\d{2})(\d{4})", filename, re.I)
        if m:
            day, month, year = m.groups()
            try:
                dt = datetime.strptime(f"{day}{month}{year}", "%d%m%Y")
                formatted = dt.strftime("%d:%m:%Y")
            except Exception:
                formatted = f"{day}:{month}:{year}"
            self.report_date_entry.configure(state="normal")
            self.report_date_entry.delete(1.0, 'end')
            self.report_date_entry.insert('end', formatted)
            self.report_date_entry.configure(state="disabled")
        else:
            self.report_date_entry.configure(state="normal")
            self.report_date_entry.delete(1.0, 'end')
            self.report_date_entry.insert('end', "Unknown")
            self.report_date_entry.configure(state="disabled")

    def load_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not path:
            return
        try:
            self.pdf_path = path
            self.pdf_doc = fitz.open(path)
            self.current_page_num = 0
            self.signature_position_pdf = None
            self.placed_signatures = {} # Clear placed signatures when new PDF is loaded

            # Ensure the canvas has its current dimensions before calculating zoom
            self.root.update_idletasks() 
            
            page = self.pdf_doc.load_page(self.current_page_num)
            
            pdf_width_pts = page.rect.width
            pdf_height_pts = page.rect.height

            # Get the effective drawable width and height of the canvas
            canvas_width_px = self.canvas_pdf.winfo_width()
            canvas_height_px = self.canvas_pdf.winfo_height()

            if pdf_width_pts == 0 or pdf_height_pts == 0 or canvas_width_px == 0 or canvas_height_px == 0:
                self.current_zoom = 1.0 # Fallback
            else:
                zoom_factor_for_width = canvas_width_px / pdf_width_pts
                zoom_factor_for_height = canvas_height_px / pdf_height_pts
                self.current_zoom = min(zoom_factor_for_width, zoom_factor_for_height)
                self.current_zoom = max(0.2, self.current_zoom) # Minimum zoom to prevent too small
                self.current_zoom = min(3.0, self.current_zoom)  # Maximum initial zoom to prevent too large


            self.render_pdf_page()
            self.set_report_date_from_filename(path)
            self.log_error("")
        except Exception as e:
            self.log_error(f"Failed to load PDF: {e}")
            self.pdf_doc = None
            self.canvas_pdf.delete("all")
            self.canvas_pdf.create_text(
                self.canvas_pdf.winfo_width() / 2, self.canvas_pdf.winfo_height() / 2,
                text="PDF PORTAL", font=("Inter", 18, "bold"), fill="#808080", tags="pdf_portal_text"
            )

    def render_pdf_page(self):
        if not self.pdf_doc:
            if not self.canvas_pdf.find_withtag("pdf_portal_text"):
                self.canvas_pdf.create_text(
                    self.canvas_pdf.winfo_width() / 2, self.canvas_pdf.winfo_height() / 2,
                    text="PDF PORTAL", font=("Inter", 18, "bold"), fill="#808080", tags="pdf_portal_text"
                )
            return

        self.canvas_pdf.delete("pdf_portal_text")
        self.canvas_pdf.delete("sig_preview_rect")
        self.canvas_pdf.delete("sig_preview_img")
        self.canvas_pdf.delete("sig_display_top_right")

        page = self.pdf_doc.load_page(self.current_page_num)
        mat = fitz.Matrix(self.current_zoom, self.current_zoom)
        pix = page.get_pixmap(matrix=mat)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.pdf_img_tk = ImageTk.PhotoImage(img)

        self.canvas_pdf.delete("all")
        self.canvas_pdf.config(scrollregion=(0, 0, pix.width, pix.height))
        
        self.canvas_pdf.create_image(0, 0, anchor="nw", image=self.pdf_img_tk)

        # Draw all currently 'placed' signatures for the current page
        if self.current_page_num in self.placed_signatures:
            for sig_info in self.placed_signatures[self.current_page_num]:
                pil_img_placed = sig_info['pil_img']
                pdf_x_placed, pdf_y_placed = sig_info['position'] # pdf_y_placed is bottom-left origin

                sig_height_pt_placed = sig_info['target_height_pt']

                # Convert PDF bottom-left origin (pdf_x_placed, pdf_y_placed)
                # to Tkinter canvas top-left origin for drawing.
                # canvas_y = (page_height_in_pixels) - (sig_bottom_y_in_pixels + sig_height_in_pixels)
                page_height_pdf_pts = page.rect.height # Get actual page height in PDF points
                canvas_x_for_placed = pdf_x_placed * self.current_zoom
                canvas_y_for_placed = (page_height_pdf_pts - (pdf_y_placed + sig_height_pt_placed)) * self.current_zoom


                placed_preview_width_on_canvas = sig_info['target_width_pt'] * self.current_zoom
                placed_preview_height_on_canvas = sig_info['target_height_pt'] * self.current_zoom
                
                if placed_preview_width_on_canvas > 0 and placed_preview_height_on_canvas > 0:
                    scaled_pil_placed_sig = pil_img_placed.resize(
                        (int(placed_preview_width_on_canvas), int(placed_preview_height_on_canvas)), Image.LANCZOS
                    )
                    sig_info['tk_img_on_canvas'] = ImageTk.PhotoImage(scaled_pil_placed_sig)
                    self.canvas_pdf.create_image(
                        canvas_x_for_placed, canvas_y_for_placed,
                        anchor="nw",
                        image=sig_info['tk_img_on_canvas'],
                        tags=f"placed_sig_{sig_info['name']}_{id(sig_info)}" 
                    )
                    self.canvas_pdf.create_rectangle(
                        canvas_x_for_placed, canvas_y_for_placed,
                        canvas_x_for_placed + placed_preview_width_on_canvas,
                        canvas_y_for_placed + placed_preview_height_on_canvas,
                        outline="gray", width=1, dash=(2,2),
                        tags=f"placed_sig_border_{id(sig_info)}"
                    )

        # Show active signature preview at top right if one is selected for manual placement
        if self.current_active_signature_data['tk_img']:
            canvas_width = self.canvas_pdf.winfo_width()
            if canvas_width <= 1:
                canvas_width = self.root.winfo_width() / 2 - 10
            
            active_tk_img = self.current_active_signature_data['tk_img']
            self.canvas_pdf.create_image(
                canvas_width - active_tk_img.width() - 10,
                10,
                anchor="nw",
                image=active_tk_img,
                tags="sig_display_top_right"
            )

    def zoom_in(self):
        if self.pdf_doc and self.current_zoom < 4.0:
            self.current_zoom *= 1.25
            self.render_pdf_page()
            # Adjust view to keep center relatively stable after zoom
            self.canvas_pdf.xview_moveto(self.canvas_pdf.xview()[0] / 1.25)
            self.canvas_pdf.yview_moveto(self.canvas_pdf.yview()[0] / 1.25)

    def zoom_out(self):
        if self.pdf_doc and self.current_zoom > 0.25:
            self.current_zoom /= 1.25
            self.render_pdf_page()
            # Adjust view to keep center relatively stable after zoom
            self.canvas_pdf.xview_moveto(self.canvas_pdf.xview()[0] * 1.25)
            self.canvas_pdf.yview_moveto(self.canvas_pdf.yview()[0] * 1.25)

    def on_drag_start(self, event):
        """Records the starting coordinates for dragging and changes cursor."""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = False # Reset drag flag
        self.canvas_pdf.config(cursor="hand2") # Change cursor to hand

    def on_drag_motion(self, event):
        """Drags the canvas view based on mouse motion."""
        if self.drag_start_x is not None and self.drag_start_y is not None:
            # Check if motion exceeds threshold to confirm a drag
            if not self.is_dragging and (abs(event.x - self.drag_start_x) > self.drag_threshold or \
                                        abs(event.y - self.drag_start_y) > self.drag_threshold):
                self.is_dragging = True

            if self.is_dragging:
                dx = event.x - self.drag_start_x
                dy = event.y - self.drag_start_y
                
                # Scroll the canvas content
                self.canvas_pdf.xview_scroll(-dx, "units")
                self.canvas_pdf.yview_scroll(-dy, "units")
                
                # Update drag start points to current mouse position for continuous dragging
                self.drag_start_x = event.x
                self.drag_start_y = event.y

    def on_drag_end(self, event):
        """Resets cursor and handles signature placement if it was a click."""
        self.canvas_pdf.config(cursor="cross") # Reset cursor to crosshair
        if not self.is_dragging: # If it wasn't a drag (i.e., it was a click)
            self._place_signature_on_click(event)
        
        self.drag_start_x = None # Clear drag start coordinates
        self.drag_start_y = None
        self.is_dragging = False # Reset drag flag


    def _place_signature_on_click(self, event):
        """Helper to place signature if the mouse event was a click (not a drag)."""
        if not self.pdf_doc or not self.current_active_signature_data['pil_img']:
            self.log_error("Load a PDF and select/load a signature to place it manually. (Hint: Use dropdowns to select a name first).")
            return

        canvas_click_x = self.canvas_pdf.canvasx(event.x)
        canvas_click_y = self.canvas_pdf.canvasy(event.y)

        page = self.pdf_doc.load_page(self.current_page_num)
        page_height_pdf_pts = page.rect.height

        # Convert canvas pixel coordinates to PDF points (scaled)
        pdf_x_top_left_click = canvas_click_x / self.current_zoom
        pdf_y_top_left_click = canvas_click_y / self.current_zoom # This is Y from top of PDF page, scaled

        sig_pil = self.current_active_signature_data['pil_img']
        sig_target_width_pt = 80 # Consistent signature width
        sig_pil_aspect_ratio = sig_pil.height / sig_pil.width
        sig_target_height_pt = sig_target_width_pt * sig_pil_aspect_ratio

        # Convert canvas top-left click Y to PDF bottom-left Y for merge
        pdf_y_bottom_left_for_merge = page_height_pdf_pts - (pdf_y_top_left_click + sig_target_height_pt)

        self.signature_position_pdf = (pdf_x_top_left_click, pdf_y_bottom_left_for_merge) 
        self.log_error(f"Manual placement position set at PDF coords: ({pdf_x_top_left_click:.1f}, {pdf_y_bottom_left_for_merge:.1f}) (size: {sig_target_width_pt}x{sig_target_height_pt:.1f} pts). Click 'APPLY ESIGN'.")

        self.canvas_pdf.delete("sig_preview_rect")
        self.canvas_pdf.delete("sig_preview_img")
        # self.canvas_pdf.delete("sig_display_top_right") # Keep top-right preview of active signature

        preview_width_on_canvas = sig_target_width_pt * self.current_zoom
        preview_height_on_canvas = sig_target_height_pt * self.current_zoom

        scaled_pil_sig_for_preview = sig_pil.resize(
            (int(preview_width_on_canvas), int(preview_height_on_canvas)), Image.LANCZOS
        )
        self.temp_scaled_sig_tk = ImageTk.PhotoImage(scaled_pil_sig_for_preview) 

        self.canvas_pdf.create_image(canvas_click_x, canvas_click_y, anchor="nw", image=self.temp_scaled_sig_tk, tags="sig_preview_img")

        self.canvas_pdf.create_rectangle(
            canvas_click_x, canvas_click_y,
            canvas_click_x + preview_width_on_canvas,
            canvas_click_y + preview_height_on_canvas,
            outline="red", width=2, tags="sig_preview_rect"
        )

    def _on_officer_dropdown_selected(self, event):
        """
        Callback for any of the officer role dropdowns being selected.
        Updates self.selected_officer_assignments and sets the active signature for manual placement.
        """
        selected_dropdown_widget = event.widget
        selected_name = selected_dropdown_widget.get()

        role_title_found = None
        for role_title, dropdown_widget in self.officer_dropdowns.items():
            if dropdown_widget == selected_dropdown_widget:
                role_title_found = role_title
                break

        if role_title_found:
            if selected_name != "--Please select Name--":
                self.selected_officer_assignments[role_title_found] = selected_name
                self.log_error(f"'{selected_name}' selected for '{role_title_found}'. This will be placed when 'LOAD SIGNATURE' is clicked. Active for manual placement: '{selected_name}'.")
            else:
                if role_title_found in self.selected_officer_assignments:
                    del self.selected_officer_assignments[role_title_found]
                self.log_error(f"'{role_title_found}' selection cleared. Names for auto-placement: {list(self.selected_officer_assignments.values())}")
        else:
            self.log_error("Could not identify the changed dropdown role.")

        if selected_name != "--Please select Name--":
            try:
                if selected_name not in self.loaded_signatures_cache:
                    conn = mysql.connector.connect(host="localhost", user="root", password="password", database="project")
                    cursor = conn.cursor()
                    cursor.execute("SELECT ESIGN FROM iocl WHERE name=%s", (selected_name,))
                    result = cursor.fetchone()
                    cursor.close()
                    conn.close()

                    if not result or not result[0]:
                        self.log_error(f"No signature image found for '{selected_name}'.")
                        self.current_active_signature_data = {'pil_img': None, 'tk_img': None, 'name': None, 'image_bytes': None}
                        self.canvas_pdf.delete("sig_display_top_right")
                        return

                    img_bytes = result[0]
                    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                    fixed_preview_width = 150
                    fixed_preview_height = int(pil_img.height * (fixed_preview_width / pil_img.width))
                    tk_img_for_preview = ImageTk.PhotoImage(pil_img.resize((fixed_preview_width, fixed_preview_height), Image.LANCZOS))
                    
                    self.loaded_signatures_cache[selected_name] = {
                        'pil_img': pil_img, 'tk_img': tk_img_for_preview, 'name': selected_name, 'image_bytes': img_bytes
                    }
                
                cached_data = self.loaded_signatures_cache[selected_name]
                self.current_active_signature_data = {
                    'pil_img': cached_data['pil_img'],
                    'tk_img': cached_data['tk_img'],
                    'name': selected_name,
                    'image_bytes': cached_data['image_bytes']
                }
                self.render_pdf_page()
            except Exception as e:
                self.log_error(f"Error loading single signature preview for '{selected_name}': {e}")
                self.current_active_signature_data = {'pil_img': None, 'tk_img': None, 'name': None, 'image_bytes': None}
                self.canvas_pdf.delete("sig_display_top_right")
        else:
            self.current_active_signature_data = {'pil_img': None, 'tk_img': None, 'name': None, 'image_bytes': None}
            self.canvas_pdf.delete("sig_display_top_right")

    def load_signature(self):
        """Automated placement of selected signatures based on predefined coordinates."""
        if not self.pdf_doc:
            self.log_error("No PDF loaded.")
            return
        if not self.selected_officer_assignments:
            self.log_error("No officers selected from dropdowns for auto-placement. Select names first.")
            return

        self.placed_signatures = {}

        placement_count = 0
        errors_during_placement = []

        page = self.pdf_doc.load_page(self.current_page_num)
        page_height_pdf_pts = page.rect.height
        sig_target_width_pt = 80

        for role_title, name_to_place in self.selected_officer_assignments.items():
            if role_title not in self.esign_coordinates:
                errors_during_placement.append(f"No predefined coordinates for role: '{role_title}'. Skipping '{name_to_place}'.")
                continue

            try:
                pil_img = None
                if name_to_place in self.loaded_signatures_cache:
                    pil_img = self.loaded_signatures_cache[name_to_place]['pil_img']
                else:
                    conn = mysql.connector.connect(host="localhost", user="root", password="password", database="project")
                    cursor = conn.cursor()
                    cursor.execute("SELECT ESIGN FROM iocl WHERE name=%s", (name_to_place,))
                    result = cursor.fetchone() 
                    cursor.close()
                    conn.close()

                    if not result or not result[0]:
                        errors_during_placement.append(f"No signature image found for '{name_to_place}'. Skipping placement.")
                        continue
                    
                    img_bytes = result[0]
                    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

                    fixed_preview_width = 150
                    fixed_preview_height = int(pil_img.height * (fixed_preview_width / pil_img.width))
                    tk_img_for_preview = ImageTk.PhotoImage(pil_img.resize((fixed_preview_width, fixed_preview_height), Image.LANCZOS))
                    self.loaded_signatures_cache[name_to_place] = {
                        'pil_img': pil_img, 'tk_img': tk_img_for_preview, 'name': name_to_place, 'image_bytes': img_bytes
                    }

                # Use the coordinates directly as they are assumed to be (x from left, y from bottom)
                pdf_x, pdf_y = self.esign_coordinates[role_title]
                
                sig_pil_aspect_ratio = pil_img.height / pil_img.width
                sig_target_height_pt = sig_target_width_pt * sig_pil_aspect_ratio
                
                placement_position = (pdf_x, pdf_y) # Directly use the provided bottom-left coordinate

                if self.current_page_num not in self.placed_signatures:
                    self.placed_signatures[self.current_page_num] = []
                
                self.placed_signatures[self.current_page_num].append({
                    'pil_img': pil_img,
                    'position': placement_position,
                    'target_width_pt': sig_target_width_pt,
                    'target_height_pt': sig_target_height_pt,
                    'name': name_to_place
                })
                placement_count += 1

            except Exception as e:
                errors_during_placement.append(f"Error placing signature for '{name_to_place}' ({role_title}): {e}")

        if errors_during_placement:
            self.log_error(f"Completed placing {placement_count} signature(s). Issues encountered:\n" + "\n".join(errors_during_placement))
        else:
            self.log_error(f"Successfully placed {placement_count} signature(s). Click 'SAVE PDF' to finalize.")
        
        self.render_pdf_page()

    def apply_signature(self):
        """Applies the manually positioned active signature."""
        if not self.pdf_doc:
            self.log_error("No PDF loaded.")
            return
        if not self.signature_position_pdf:
            self.log_error("Click on the PDF to set manual signature position before applying.")
            return
        if not self.current_active_signature_data['pil_img']:
            self.log_error("No active signature selected/loaded for manual placement. Select a name from dropdown first.")
            return

        active_pil_img = self.current_active_signature_data['pil_img']
        active_name = self.current_active_signature_data['name']

        sig_target_width_pt = 80
        sig_pil_aspect_ratio = active_pil_img.height / active_pil_img.width
        sig_target_height_pt = sig_target_width_pt * sig_pil_aspect_ratio

        if self.current_page_num not in self.placed_signatures:
            self.placed_signatures[self.current_page_num] = []
        
        self.placed_signatures[self.current_page_num].append({
            'pil_img': active_pil_img,
            'position': self.signature_position_pdf, # This is already bottom-left origin from _place_signature_on_click
            'target_width_pt': sig_target_width_pt,
            'target_height_pt': sig_target_height_pt,
            'name': active_name
        })

        self.signature_position_pdf = None
        self.log_error(f"Manually placed signature '{active_name}' on page {self.current_page_num + 1}. Click on PDF to place another or 'SAVE PDF'.")
        self.render_pdf_page()

    def save_pdf(self):
        if not self.pdf_doc:
            self.log_error("No PDF to save.")
            return
        if not self.placed_signatures:
            self.log_error("No signatures have been placed on the PDF yet. Nothing to save.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            title="Save PDF as"
        )
        if not save_path:
            return

        try:
            from PyPDF2 import PdfFileReader, PdfFileWriter
            from reportlab.pdfgen import canvas as rp_canvas
            from reportlab.lib.utils import ImageReader

            original_pdf_bytes = self.pdf_doc.tobytes()
            reader = PdfFileReader(io.BytesIO(original_pdf_bytes))
            writer = PdfFileWriter()

            for i in range(reader.getNumPages()):
                page = reader.getPage(i)
                
                if i in self.placed_signatures:
                    for sig_info in self.placed_signatures[i]:
                        pil_img_to_merge = sig_info['pil_img']
                        pos_x, pos_y = sig_info['position']
                        target_width_pt = sig_info['target_width_pt']
                        target_height_pt = sig_info['target_height_pt']

                        packet = io.BytesIO()
                        c = rp_canvas.Canvas(packet, pagesize=(target_width_pt, target_height_pt))
                        c.drawImage(
                            ImageReader(pil_img_to_merge.resize((int(target_width_pt), int(target_height_pt)), Image.LANCZOS)),
                            0, 0, width=target_width_pt, height=target_height_pt, mask='auto'
                        )
                        c.save()
                        packet.seek(0)
                        
                        sig_reader = PdfFileReader(packet)
                        sig_page = sig_reader.getPage(0)

                        page.mergeTransformedPage(
                            sig_page,
                            (1, 0, 0, 1, pos_x, pos_y)
                        )

                writer.addPage(page)

            with open(save_path, "wb") as output_file:
                writer.write(output_file)

            self.pdf_doc.close()
            self.pdf_doc = fitz.open(save_path)
            self.current_zoom = 1.0
            self.current_page_num = 0
            self.signature_position_pdf = None
            self.placed_signatures = {}
            self.render_pdf_page()
            self.log_error(f"PDF saved successfully with all signatures: {save_path}")
            messagebox.showinfo("Saved", f"PDF saved successfully:\n{save_path}")

        except Exception as e:
            self.log_error(f"Error saving PDF with signatures: {e}\n\n"
                            f"Please ensure:\n"
                            f"1. PyPDF2 (version 2.12.1 suggested for this code) is installed (pip install PyPDF2==2.12.1)\n"
                            f"2. ReportLab is installed (pip install reportlab)\n"
                            f"If issues persist, consider a clean reinstallation: pip uninstall PyPDF2; pip install PyPDF2==2.12.1")

def main():
    root = Tk()
    app = HSEReportPortalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
