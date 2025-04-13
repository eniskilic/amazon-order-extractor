import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import inch
from pdf2image import convert_from_bytes
from PIL import Image

LABEL_SIZE = (4 * inch, 6 * inch)

# ==================== STREAMLIT UI ====================
st.set_page_config(page_title="Amazon Order Page Snapshots", layout="wide")
st.title("📦 Amazon Orders — 4x6 Image-Based PDF Generator")

uploaded_file = st.file_uploader("Upload a single Amazon Order PDF", type="pdf")

if uploaded_file:
    st.success("PDF uploaded. Generating images...")

    # Convert entire PDF to images
    images = convert_from_bytes(uploaded_file.read(), dpi=200)
    st.info(f"Extracted {len(images)} page(s).")

    output_pdf = BytesIO()
    c = canvas.Canvas(output_pdf, pagesize=LABEL_SIZE)

    order_blocks = []
    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            orders = text.split("Shipping Address:")[1:]
            for j, order_text in enumerate(orders):
                order_blocks.append((i, order_text.strip()))

    # Add one cropped image per order block (approx layout)
    for index, (page_index, _) in enumerate(order_blocks):
        img = convert_from_bytes(uploaded_file.getvalue(), first_page=page_index+1, last_page=page_index+1, dpi=200)[0]

        # Resize to fit 4x6 and center
        img = img.resize((int(4 * inch), int(6 * inch)))
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)

        # Draw on canvas
        c.drawImage(Image.open(img_io), 0, 0, width=LABEL_SIZE[0], height=LABEL_SIZE[1])
        c.showPage()

    # Final full page as reference
    fullpage_img = images[0].resize((int(4 * inch), int(6 * inch)))
    img_buffer = BytesIO()
    fullpage_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    c.drawImage(Image.open(img_buffer), 0, 0, width=LABEL_SIZE[0], height=LABEL_SIZE[1])
    c.showPage()

    c.save()
    output_pdf.seek(0)

    st.download_button("📥 Download 4x6 PDF Snapshot of Orders", data=output_pdf, file_name="Amazon_Order_Snapshots.pdf", mime="application/pdf")
