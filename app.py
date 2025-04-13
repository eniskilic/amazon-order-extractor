import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import inch

PAGE_WIDTH, PAGE_HEIGHT = A6  # 4.1 x 5.8 in approx

# ============ CLEAN FIELD UTILS ============

def clean_thread_color(raw):
    return re.sub(r'\s*\(#\w+\)', '', raw).strip()

def clean_product_title(raw):
    # Remove "Unit price" lines or anything after "Item total"
    raw = re.sub(r'Unit price.*', '', raw)
    raw = re.sub(r'Item total.*', '', raw)
    return raw.strip()

def clean_address(raw):
    return re.sub(r'Buyer Name:.*', '', raw).strip()

# ============ PDF ORDER EXTRACTION ============

def extract_orders_from_pdfs(pdf_files):
    towel_orders, blanket_orders = [], []

    for pdf_file in pdf_files:
        with pdfplumber.open(pdf_file) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)

        raw_orders = text.split("Shipping Address:")[1:]

        for raw in raw_orders:
            base = {}
            addr_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", raw)
            if addr_match:
                base['Buyer Name'] = addr_match.group(1).strip()
                base['Address'] = clean_address(f"{addr_match.group(2).strip()}, {addr_match.group(3).strip()}")

            base['Order ID'] = re.search(r"Order ID:\s*([\d\-]+)", raw).group(1) if re.search(r"Order ID:\s*([\d\-]+)", raw) else ""
            base['Order Item ID'] = re.search(r"Order Item ID:\s*(\d+)", raw).group(1) if re.search(r"Order Item ID:\s*(\d+)", raw) else ""
            base['SKU'] = re.search(r"SKU:\s*(.+?)\n", raw).group(1).strip() if re.search(r"SKU:\s*(.+?)\n", raw) else ""
            base['FNSKU'] = re.search(r"FNSKU:\s*([A-Z0-9]+)", raw).group(1).strip() if re.search(r"FNSKU:\s*([A-Z0-9]+)", raw) else ""

            title_match = re.search(r"Product Details\s*(.*?)\s*SKU:", raw, re.DOTALL)
            base['Product Title'] = clean_product_title(title_match.group(1).replace('\n', ' ')) if title_match else ""

            base['Qty'] = re.search(r"Quantity\s*(\d+)", raw).group(1) if re.search(r"Quantity\s*(\d+)", raw) else "1"

            gift_note_match = re.search(r"Gift (Message|Note):\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
            gift_note = gift_note_match.group(2).strip() if gift_note_match else ""

            if "towel" in raw.lower():
                towel = base.copy()
                towel['Set Type'] = "3pc" if "3Pcs" in raw else ""
                towel['Font'] = re.search(r"Choose Your Font:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Choose Your Font:\s*([^\n]+)", raw) else ""
                towel['Font Color'] = re.search(r"Font Color:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Font Color:\s*([^\n]+)", raw) else ""
                for t in ['Washcloth', 'Hand Towel', 'Bath Towel']:
                    match = re.search(rf"{t}:\s*(.+)", raw)
                    towel[f'{t} Text'] = match.group(1).strip() if match else ""
                towel['Gift Note'] = gift_note
                towel_orders.append(towel)

            elif "blanket" in raw.lower():
                blanket = base.copy()
                blanket['Blanket Color'] = re.search(r"Blanket Color:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Blanket Color:\s*([^\n]+)", raw) else ""
                blanket['Font'] = re.search(r"Font:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Font:\s*([^\n]+)", raw) else ""
                thread_raw = re.search(r"Thread Color:\s*([^\n]+)", raw)
                blanket['Thread Color'] = clean_thread_color(thread_raw.group(1)) if thread_raw else ""
                blanket['Name'] = re.search(r"Blanket Text:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Blanket Text:\s*([^\n]+)", raw) else ""
                blanket['Knit Hat?'] = re.search(r"Knit Hat:\s*(Yes|No)", raw, re.IGNORECASE).group(1).strip() if re.search(r"Knit Hat:\s*(Yes|No)", raw, re.IGNORECASE) else "No"
                giftbox_match = re.search(r"Gift Box:\s*(Yes|No)", raw, re.IGNORECASE)
                blanket['Gift Box?'] = "Yes" if gift_note else (giftbox_match.group(1).strip() if giftbox_match else "No")
                blanket['Gift Note'] = gift_note
                blanket_orders.append(blanket)

    return pd.DataFrame(towel_orders), pd.DataFrame(blanket_orders)

# ============ LABEL BUILDER ============

def create_labels_pdf(towel_df, blanket_df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    def write(label, value, bold=True, size=8, gap=12):
        nonlocal y
        if not value: return
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(25, y, f"{label}:" if bold else value)
        if not bold:
            c.drawString(90, y, value)
        y -= gap

    def wrap(label, text, max_chars=65):
        nonlocal y
        if not text: return
        c.setFont("Helvetica-Bold", 8)
        c.drawString(25, y, f"{label}:")
        y -= 10
        c.setFont("Helvetica", 8)
        for line in [text[i:i+max_chars] for i in range(0, len(text), max_chars)]:
            c.drawString(30, y, line.strip())
            y -= 10
        y -= 4

    for df, label in [(towel_df, "🧺 TOWEL ORDER"), (blanket_df, "🍼 BLANKET ORDER")]:
        for row in df.to_dict(orient='records'):
            y = PAGE_HEIGHT - 30
            c.setFont("Helvetica-Bold", 12)
            c.drawString(25, y, label)
            y -= 18
            write("Buyer", row.get("Buyer Name", ""))
            write("Address", row.get("Address", ""))
            write("Order ID", row.get("Order ID", ""))
            wrap("Product", row.get("Product Title", ""))
            write("FNSKU", row.get("FNSKU", ""), bold=False)
            write("SKU", row.get("SKU", ""), bold=False)
            write("Qty", row.get("Qty", ""))
            write("Set Type", row.get("Set Type", ""))

            if label == "🧺 TOWEL ORDER":
                write("Font", row.get("Font", ""))
                write("Font Color", row.get("Font Color", ""))
                write("Washcloth", row.get("Washcloth Text", ""))
                write("Hand Towel", row.get("Hand Towel Text", ""))
                write("Bath Towel", row.get("Bath Towel Text", ""))
            else:
                write("Blanket Color", row.get("Blanket Color", ""))
                write("Font", row.get("Font", ""))
                write("Thread Color", row.get("Thread Color", ""))
                write("Name", row.get("Name", ""))
                write("Knit Hat", row.get("Knit Hat?"))
                write("Gift Box", row.get("Gift Box?"))

            wrap("Gift Note", row.get("Gift Note", ""))
            c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# ============ STREAMLIT UI ============

st.set_page_config(page_title="Amazon Order Labels", layout="wide")
st.title("📦 Amazon Order Extractor + Printable Labels")

uploaded_files = st.file_uploader("Upload Amazon Order PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    towels_df, blankets_df = extract_orders_from_pdfs(uploaded_files)

    if not towels_df.empty:
        st.subheader("🧺 Towel Orders")
        st.dataframe(towels_df, use_container_width=True)

    if not blankets_df.empty:
        st.subheader("🍼 Blanket Orders")
        st.dataframe(blankets_df, use_container_width=True)

    # Excel download
    excel_io = BytesIO()
    with pd.ExcelWriter(excel_io, engine="openpyxl") as writer:
        if not towels_df.empty:
            towels_df.to_excel(writer, index=False, sheet_name="Towels")
        if not blankets_df.empty:
            blankets_df.to_excel(writer, index=False, sheet_name="Blankets")
    excel_io.seek(0)

    st.download_button("📥 Download Excel (2 Sheets)", data=excel_io, file_name="Amazon_Orders.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if st.button("📄 Generate Labels PDF"):
        label_pdf = create_labels_pdf(towels_df, blankets_df)
        st.download_button("📥 Download PDF Labels", data=label_pdf, file_name="Amazon_Labels.pdf", mime="application/pdf")

    if st.button("🔄 Reset"):
        st.experimental_rerun()
