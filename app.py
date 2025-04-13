import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

LABEL_SIZE = (4 * inch, 6 * inch)  # 4x6 inches portrait

# ==================== DATA EXTRACTION ====================
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

            date_match = re.search(r"Order Date:\s*(\w{3},\s\w{3}\s\d{1,2},\s\d{4})", raw)
            base['Order Date'] = date_match.group(1) if date_match else ""

            order_id_match = re.search(r"Order ID:\s*(\d{3}-\d{7}-\d{7})", raw)
            base['Order ID'] = order_id_match.group(1) if order_id_match else ""

            item_id_match = re.search(r"Order Item ID:\s*(\d+)", raw)
            base['Order Item ID'] = item_id_match.group(1) if item_id_match else ""

            sku_match = re.search(r"SKU:\s*(.+?)\n", raw)
            base['SKU'] = sku_match.group(1).strip() if sku_match else ""

            qty_match = re.search(r"Quantity\s*(\d+)", raw)
            base['Qty'] = qty_match.group(1) if qty_match else "1"

            gift_note_match = re.search(r"Gift (Message|Note):\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
            gift_note = gift_note_match.group(2).strip() if gift_note_match else ""

            if re.search(r"towel|washcloth|hand towel|bath towel", raw, re.IGNORECASE):
                towel = base.copy()

                if "2Pcs" in raw:
                    towel['Set Type'] = "2pc"
                elif "3Pcs" in raw:
                    towel['Set Type'] = "3pc"
                elif "6Pcs" in raw:
                    towel['Set Type'] = "6pc"
                elif "Hand Towel" in raw:
                    towel['Set Type'] = "Hand"
                else:
                    towel['Set Type'] = ""

                font_match = re.search(r"Choose Your Font:\s*([^\n]+)", raw)
                towel['Font'] = font_match.group(1).strip() if font_match else ""

                color_match = re.search(r"Font Color:\s*([^\(#\n]+)", raw)
                towel['Font Color'] = color_match.group(1).strip() if color_match else ""

                for t in ['Washcloth', 'Hand Towel', 'Bath Towel']:
                    match = re.search(rf"{t}:\s*(.+)", raw)
                    towel[f'{t} Text'] = match.group(1).strip() if match else ""

                towel['Gift Note'] = gift_note
                towel_orders.append(towel)

            elif re.search(r"blanket|swaddle|beanie|knit hat", raw, re.IGNORECASE):
                blanket = base.copy()

                color_match = re.search(r"Blanket Color:\s*([^\n]+)", raw)
                blanket['Blanket Color'] = color_match.group(1).strip() if color_match else ""

                font_match = re.search(r"Font:\s*([^\n]+)", raw)
                blanket['Font'] = font_match.group(1).strip() if font_match else ""

                thread_match = re.search(r"Thread Color:\s*([^\n]+)", raw)
                blanket['Thread Color'] = thread_match.group(1).strip() if thread_match else ""

                name_match = re.search(r"Blanket Text:\s*([^\n]+)", raw)
                blanket['Name'] = name_match.group(1).strip() if name_match else ""

                hat_match = re.search(r"Knit Hat:\s*(Yes|No)", raw, re.IGNORECASE)
                blanket['Knit Hat?'] = hat_match.group(1).strip().capitalize() if hat_match else "No"

                giftbox_match = re.search(r"Gift Box:\s*(Yes|No)", raw, re.IGNORECASE)
                gift_box_value = "Yes" if gift_note else (
                    giftbox_match.group(1).strip().capitalize() if giftbox_match else "No"
                )

                blanket['Gift Box?'] = gift_box_value
                blanket['Gift Note'] = gift_note

                blanket_orders.append(blanket)

    return pd.DataFrame(towel_orders), pd.DataFrame(blanket_orders)

# ==================== LABEL GENERATOR ====================
def create_4x6_labels_pdf(towel_df, blanket_df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LABEL_SIZE)
    c.setTitle("Amazon Order Labels")

    def draw_text(label, value, size=12, bold=False, gap=15):
        if value:
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawString(40, draw_text.y, f"{label}: {value}")
            draw_text.y -= gap

    for row in towel_df.to_dict(orient='records'):
        draw_text.y = 560
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, draw_text.y, "🧺 TOWEL ORDER")
        draw_text.y -= 30

        draw_text("Buyer", row['Buyer Name'], 11)
        draw_text("", row['Address'], 10)
        draw_text("Order ID", row['Order ID'])
        draw_text("Qty", row['Qty'], gap=12)
        draw_text("Set", row['Set Type'], gap=12)
        draw_text("SKU", row['SKU'], size=10, gap=12)

        draw_text("Font", row['Font'], bold=True)
        draw_text("Font Color", row['Font Color'], bold=True)

        draw_text("Washcloth", row.get('Washcloth Text', ''), bold=True)
        draw_text("Hand Towel", row.get('Hand Towel Text', ''), bold=True)
        draw_text("Bath Towel", row.get('Bath Towel Text', ''), bold=True)

        if row.get('Gift Note'):
            draw_text("Gift Note", f'"{row["Gift Note"]}"', size=10, gap=18)

        c.showPage()

    for row in blanket_df.to_dict(orient='records'):
        draw_text.y = 560
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, draw_text.y, "🍼 BLANKET ORDER")
        draw_text.y -= 30

        draw_text("Buyer", row['Buyer Name'], 11)
        draw_text("", row['Address'], 10)
        draw_text("Order ID", row['Order ID'])
        draw_text("Qty", row['Qty'], gap=12)
        draw_text("SKU", row['SKU'], size=10, gap=12)

        draw_text("Blanket Color", row.get("Blanket Color", ""), bold=True)
        draw_text("Font", row.get("Font", ""), bold=True)
        draw_text("Thread", row.get("Thread Color", ""), bold=True)
        draw_text("Name", row.get("Name", ""), bold=True)

        draw_text("Knit Hat", row.get("Knit Hat?"))
        draw_text("Gift Box", row.get("Gift Box?"))
        if row.get("Gift Note"):
            draw_text("Gift Note", f'"{row["Gift Note"]}"', size=10, gap=18)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# ==================== STREAMLIT APP ====================
st.set_page_config(page_title="Amazon Orders Split", layout="wide")
st.title("📦 Amazon Custom Orders — Towels & Blankets")

uploaded_files = st.file_uploader("Upload one or more Amazon Order PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    towels_df, blankets_df = extract_orders_from_pdfs(uploaded_files)

    if not towels_df.empty:
        st.subheader("🧺 Towel Orders")
        st.dataframe(towels_df, use_container_width=True)

    if not blankets_df.empty:
        st.subheader("🍼 Blanket Orders")
        st.dataframe(blankets_df, use_container_width=True)

    # Excel Export
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        if not towels_df.empty:
            towels_df.to_excel(writer, sheet_name='Towels', index=False)
        if not blankets_df.empty:
            blankets_df.to_excel(writer, sheet_name='Blankets', index=False)
    excel_buffer.seek(0)

    st.download_button("📥 Download Excel (2 Sheets)", excel_buffer, file_name="Amazon_Orders.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Label PDF
    if st.button("📄 Generate 4x6 Order Labels PDF"):
        label_pdf = create_4x6_labels_pdf(towels_df, blankets_df)
        st.download_button("📥 Download Printable 4x6 Labels", data=label_pdf, file_name="Amazon_Order_Labels_4x6.pdf", mime="application/pdf")

    if st.button("🔄 Clear All"):
        st.experimental_rerun()
