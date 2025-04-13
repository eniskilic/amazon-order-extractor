import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch

LABEL_WIDTH = 4 * inch
LABEL_HEIGHT = 6 * inch
LABEL_SIZE = (LABEL_WIDTH, LABEL_HEIGHT)

# ======================= PDF EXTRACTION =======================
def extract_orders_from_pdfs(pdf_files):
    combined_orders = {}
    towel_rows, blanket_rows = [], []

    for file in pdf_files:
        with pdfplumber.open(file) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)

        chunks = text.split("Shipping Address:")[1:]
        for chunk in chunks:
            base = {}
            addr_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", chunk)
            if addr_match:
                base['Buyer Name'] = addr_match.group(1).strip()
                base['Address'] = f"{addr_match.group(2).strip()}, {addr_match.group(3).strip()}"

            base['Order ID'] = re.search(r"Order ID:\s*([\d\-]+)", chunk).group(1) if re.search(r"Order ID:\s*([\d\-]+)", chunk) else ""
            base['SKU'] = re.search(r"SKU:\s*(.+?)\n", chunk).group(1).strip() if re.search(r"SKU:\s*(.+?)\n", chunk) else ""
            base['FNSKU'] = re.search(r"FNSKU:\s*([A-Z0-9]+)", chunk).group(1).strip() if re.search(r"FNSKU:\s*([A-Z0-9]+)", chunk) else ""
            title_match = re.search(r"Product Details\s*(.*?)\s*SKU:", chunk, re.DOTALL)
            base['Product Title'] = re.sub(r"Unit price.*", "", title_match.group(1).replace('\n', ' ')).strip() if title_match else ""
            base['Qty'] = re.search(r"Quantity\s*(\d+)", chunk).group(1) if re.search(r"Quantity\s*(\d+)", chunk) else "1"
            gift_note_match = re.search(r"Gift (Message|Note):\s*(.+?)(?:\n|$)", chunk, re.IGNORECASE)
            base['Gift Note'] = gift_note_match.group(2).strip() if gift_note_match else ""

            order_id = base['Order ID']
            if order_id not in combined_orders:
                combined_orders[order_id] = base.copy()
                combined_orders[order_id]['Towel'] = {}
                combined_orders[order_id]['Blanket'] = {}

            if "towel" in chunk.lower():
                combined_orders[order_id]['Towel'].update({
                    'Set Type': "3pc" if "3Pcs" in chunk else "",
                    'Font': re.search(r"Choose Your Font:\s*([^\n]+)", chunk).group(1).strip() if re.search(r"Choose Your Font:\s*([^\n]+)", chunk) else "",
                    'Font Color': re.search(r"Font Color:\s*([^\(#\n]+)", chunk).group(1).strip() if re.search(r"Font Color:\s*([^\(#\n]+)", chunk) else "",
                    'Washcloth': re.search(r"Washcloth:\s*(.+)", chunk).group(1).strip() if re.search(r"Washcloth:\s*(.+)", chunk) else "",
                    'Hand Towel': re.search(r"Hand Towel:\s*(.+)", chunk).group(1).strip() if re.search(r"Hand Towel:\s*(.+)", chunk) else "",
                    'Bath Towel': re.search(r"Bath Towel:\s*(.+)", chunk).group(1).strip() if re.search(r"Bath Towel:\s*(.+)", chunk) else "",
                })
                towel_rows.append(combined_orders[order_id])

            elif "blanket" in chunk.lower():
                combined_orders[order_id]['Blanket'].update({
                    'Blanket Color': re.search(r"Blanket Color:\s*([^\n]+)", chunk).group(1).strip() if re.search(r"Blanket Color:\s*([^\n]+)", chunk) else "",
                    'Font': re.search(r"Font:\s*([^\n]+)", chunk).group(1).strip() if re.search(r"Font:\s*([^\n]+)", chunk) else "",
                    'Thread Color': re.sub(r"\s*\(#\w+\)", "", re.search(r"Thread Color:\s*([^\n]+)", chunk).group(1).strip()) if re.search(r"Thread Color:\s*([^\n]+)", chunk) else "",
                    'Name': re.search(r"Blanket Text:\s*([^\n]+)", chunk).group(1).strip() if re.search(r"Blanket Text:\s*([^\n]+)", chunk) else "",
                    'Gift Box': "Yes" if base['Gift Note'] else (re.search(r"Gift Box:\s*(Yes|No)", chunk).group(1).strip() if re.search(r"Gift Box:\s*(Yes|No)", chunk) else "No"),
                    'Knit Hat': re.search(r"Knit Hat:\s*(Yes|No)", chunk).group(1).strip() if re.search(r"Knit Hat:\s*(Yes|No)", chunk) else "No"
                })
                blanket_rows.append(combined_orders[order_id])

    return pd.DataFrame(towel_rows), pd.DataFrame(blanket_rows), combined_orders

# ======================= LABEL GENERATOR =======================
def create_4x6_labels(combined_orders):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LABEL_SIZE)

    for order_id, order in combined_orders.items():
        y = LABEL_HEIGHT - 30
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20, y, f"🧵 ORDER ID: {order_id}")
        y -= 15

        def draw(label, value):
            nonlocal y
            if value:
                c.setFont("Helvetica-Bold", 8)
                c.drawString(20, y, f"{label}:")
                c.setFont("Helvetica", 8)
                c.drawString(90, y, str(value))
                y -= 10

        draw("Buyer", order.get("Buyer Name"))
        draw("Address", order.get("Address"))
        draw("Product", order.get("Product Title"))
        draw("FNSKU", order.get("FNSKU"))
        draw("SKU", order.get("SKU"))
        draw("Qty", order.get("Qty"))

        if order.get("Towel"):
            c.setFont("Helvetica-Bold", 9)
            c.drawString(20, y, "--- TOWEL DETAILS ---")
            y -= 10
            for k, v in order["Towel"].items():
                draw(k, v)

        if order.get("Blanket"):
            c.setFont("Helvetica-Bold", 9)
            c.drawString(20, y, "--- BLANKET DETAILS ---")
            y -= 10
            for k, v in order["Blanket"].items():
                draw(k, v)

        if order.get("Gift Note"):
            c.setFont("Helvetica-Bold", 8)
            c.drawString(20, y, "Gift Note:")
            y -= 10
            c.setFont("Helvetica", 8)
            wrapped = [order["Gift Note"][i:i+60] for i in range(0, len(order["Gift Note"]), 60)]
            for line in wrapped:
                c.drawString(25, y, line)
                y -= 10

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# ======================= STREAMLIT UI =======================
st.set_page_config(page_title="Amazon Orders", layout="wide")
st.title("📦 Amazon Orders Viewer + Printable Labels")

uploaded_files = st.file_uploader("Upload one or more Amazon Order PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    towels_df, blankets_df, combined_orders = extract_orders_from_pdfs(uploaded_files)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Download Excel (Towels & Blankets)", data=pd.ExcelWriter(BytesIO(), engine='openpyxl'), key='excel_btn', help="Coming soon")
    with col2:
        label_pdf = create_4x6_labels(combined_orders)
        st.download_button("📄 Download Printable 4x6 Labels", data=label_pdf, file_name="Amazon_Labels.pdf", mime="application/pdf")

    if not towels_df.empty:
        st.subheader("🧺 Towel Orders")
        st.dataframe(towels_df, use_container_width=True)

    if not blankets_df.empty:
        st.subheader("🍼 Blanket Orders")
        st.dataframe(blankets_df, use_container_width=True)

    if st.button("🔄 Reset"):
        st.experimental_rerun()
