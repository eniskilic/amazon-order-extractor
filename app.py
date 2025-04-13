import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import inch

PAGE_WIDTH, PAGE_HEIGHT = A6  # approx 4.1 x 5.8 inches

def extract_orders_from_pdfs(pdf_files):
    towel_orders = []
    blanket_orders = []

    for pdf_file in pdf_files:
        with pdfplumber.open(pdf_file) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        raw_orders = text.split("Shipping Address:")[1:]

        for raw in raw_orders:
            base = {}
            addr_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", raw)
            if addr_match:
                base['Buyer Name'] = addr_match.group(1).strip()
                base['Address'] = f"{addr_match.group(2).strip()}, {addr_match.group(3).strip()}"

            order_id_match = re.search(r"Order ID:\s*(\d{3}-\d{7}-\d{7})", raw)
            base['Order ID'] = order_id_match.group(1) if order_id_match else ""

            item_id_match = re.search(r"Order Item ID:\s*(\d+)", raw)
            base['Order Item ID'] = item_id_match.group(1) if item_id_match else ""

            sku_match = re.search(r"SKU:\s*(.+?)\n", raw)
            base['SKU'] = sku_match.group(1).strip() if sku_match else ""

            fnsku_match = re.search(r"FNSKU:\s*([A-Z0-9]+)", raw)
            base['FNSKU'] = fnsku_match.group(1).strip() if fnsku_match else ""

            title_match = re.search(r"Product Details\s*(.*?)\s*SKU:", raw, re.DOTALL)
            base['Product Title'] = title_match.group(1).strip().replace('\n', ' ') if title_match else ""

            qty_match = re.search(r"Quantity\s*(\d+)", raw)
            base['Qty'] = qty_match.group(1) if qty_match else "1"

            gift_note_match = re.search(r"Gift (Message|Note):\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
            gift_note = gift_note_match.group(2).strip() if gift_note_match else ""

            if re.search(r"towel|washcloth|hand towel|bath towel", raw, re.IGNORECASE):
                towel = base.copy()
                towel['Set Type'] = "3pc" if "3Pcs" in raw else ""
                towel['Font'] = re.search(r"Choose Your Font:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Choose Your Font:\s*([^\n]+)", raw) else ""
                towel['Font Color'] = re.search(r"Font Color:\s*([^\(#\n]+)", raw).group(1).strip() if re.search(r"Font Color:\s*([^\(#\n]+)", raw) else ""
                for t in ['Washcloth', 'Hand Towel', 'Bath Towel']:
                    match = re.search(rf"{t}:\s*(.+)", raw)
                    towel[f'{t} Text'] = match.group(1).strip() if match else ""
                towel['Gift Note'] = gift_note
                towel_orders.append(towel)

            elif re.search(r"blanket|swaddle|beanie|knit hat", raw, re.IGNORECASE):
                blanket = base.copy()
                blanket['Blanket Color'] = re.search(r"Blanket Color:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Blanket Color:\s*([^\n]+)", raw) else ""
                blanket['Font'] = re.search(r"Font:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Font:\s*([^\n]+)", raw) else ""
                blanket['Thread Color'] = re.search(r"Thread Color:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Thread Color:\s*([^\n]+)", raw) else ""
                blanket['Name'] = re.search(r"Blanket Text:\s*([^\n]+)", raw).group(1).strip() if re.search(r"Blanket Text:\s*([^\n]+)", raw) else ""
                blanket['Knit Hat?'] = re.search(r"Knit Hat:\s*(Yes|No)", raw, re.IGNORECASE).group(1).strip() if re.search(r"Knit Hat:\s*(Yes|No)", raw, re.IGNORECASE) else "No"
                giftbox_match = re.search(r"Gift Box:\s*(Yes|No)", raw, re.IGNORECASE)
                blanket['Gift Box?'] = "Yes" if gift_note else (giftbox_match.group(1).strip() if giftbox_match else "No")
                blanket['Gift Note'] = gift_note
                blanket_orders.append(blanket)

    return pd.DataFrame(towel_orders), pd.DataFrame(blanket_orders)

# ============ LABEL CREATION ============

def create_1pg_labels_pdf(towel_df, blanket_df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    def draw_wrapped_text(label, value, size=8, y_offset=12):
        nonlocal y
        if not value: return
        c.setFont("Helvetica-Bold", size)
        c.drawString(20, y, f"{label}:")
        c.setFont("Helvetica", size)
        wrapped = c.beginText(60, y)
        wrapped.textLines(value)
        c.drawText(wrapped)
        y -= y_offset * max(1, len(value) // 40 + 1)

    for row in towel_df.to_dict(orient="records"):
        y = PAGE_HEIGHT - 30
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20, y, "🧺 TOWEL ORDER")
        y -= 18

        draw_wrapped_text("Buyer", row.get("Buyer Name", ""))
        draw_wrapped_text("Address", row.get("Address", ""))
        draw_wrapped_text("Order ID", row.get("Order ID", ""))
        draw_wrapped_text("Product", row.get("Product Title", ""))
        draw_wrapped_text("FNSKU", row.get("FNSKU", ""))
        draw_wrapped_text("SKU", row.get("SKU", ""))
        draw_wrapped_text("Qty", row.get("Qty", ""))
        draw_wrapped_text("Set Type", row.get("Set Type", ""))
        draw_wrapped_text("Font", row.get("Font", ""))
        draw_wrapped_text("Font Color", row.get("Font Color", ""))
        draw_wrapped_text("Washcloth", row.get("Washcloth Text", ""))
        draw_wrapped_text("Hand Towel", row.get("Hand Towel Text", ""))
        draw_wrapped_text("Bath Towel", row.get("Bath Towel Text", ""))
        draw_wrapped_text("Gift Note", row.get("Gift Note", ""))
        c.showPage()

    for row in blanket_df.to_dict(orient="records"):
        y = PAGE_HEIGHT - 30
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20, y, "🍼 BLANKET ORDER")
        y -= 18

        draw_wrapped_text("Buyer", row.get("Buyer Name", ""))
        draw_wrapped_text("Address", row.get("Address", ""))
        draw_wrapped_text("Order ID", row.get("Order ID", ""))
        draw_wrapped_text("Product", row.get("Product Title", ""))
        draw_wrapped_text("FNSKU", row.get("FNSKU", ""))
        draw_wrapped_text("SKU", row.get("SKU", ""))
        draw_wrapped_text("Qty", row.get("Qty", ""))
        draw_wrapped_text("Blanket Color", row.get("Blanket Color", ""))
        draw_wrapped_text("Font", row.get("Font", ""))
        draw_wrapped_text("Thread Color", row.get("Thread Color", ""))
        draw_wrapped_text("Name", row.get("Name", ""))
        draw_wrapped_text("Knit Hat", row.get("Knit Hat?", ""))
        draw_wrapped_text("Gift Box", row.get("Gift Box?", ""))
        draw_wrapped_text("Gift Note", row.get("Gift Note", ""))
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# ============ STREAMLIT APP ============

st.set_page_config(page_title="Amazon Order Labels", layout="wide")
st.title("🧾 Amazon Order Extractor + Printable Labels")

uploaded_files = st.file_uploader("Upload 1 or more Amazon Order PDFs", type="pdf", accept_multiple_files=True)

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

    # Label PDF
    if st.button("📄 Generate Smart-Fitting Labels"):
        label_pdf = create_1pg_labels_pdf(towels_df, blankets_df)
        st.download_button("📥 Download Labels PDF", data=label_pdf, file_name="Amazon_Labels.pdf", mime="application/pdf")

    if st.button("🔄 Reset"):
        st.experimental_rerun()
