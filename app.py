import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

def extract_orders_from_pdf(pdf_file):
    towel_orders = []
    blanket_orders = []

    with pdfplumber.open(pdf_file) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    raw_orders = text.split("Shipping Address:")[1:]

    for raw in raw_orders:
        base = {}
        # Buyer Name & Address
        addr_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", raw)
        if addr_match:
            base['Buyer Name'] = addr_match.group(1).strip()
            base['Address'] = f"{addr_match.group(2).strip()}, {addr_match.group(3).strip()}"

        # Order Date & ID
        date_match = re.search(r"Order Date:\s*(\w{3},\s\w{3}\s\d{1,2},\s\d{4})", raw)
        base['Order Date'] = date_match.group(1) if date_match else ""

        order_id_match = re.search(r"Order ID:\s*(\d{3}-\d{7}-\d{7})", raw)
        base['Order ID'] = order_id_match.group(1) if order_id_match else ""

        item_id_match = re.search(r"Order Item ID:\s*(\d+)", raw)
        base['Order Item ID'] = item_id_match.group(1) if item_id_match else ""

        # SKU
        sku_match = re.search(r"SKU:\s*(.+?)\n", raw)
        base['SKU'] = sku_match.group(1).strip() if sku_match else ""

        # Quantity
        qty_match = re.search(r"Quantity\s*(\d+)", raw)
        base['Qty'] = qty_match.group(1) if qty_match else "1"

        # Gift Note detection
        gift_note_match = re.search(r"Gift (Message|Note):\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
        gift_note = gift_note_match.group(2).strip() if gift_note_match else ""
        base["Gift Note"] = gift_note

        # Classify as Towel or Blanket
        if re.search(r"towel|washcloth|hand towel|bath towel", raw, re.IGNORECASE):
            towel = base.copy()

            # Set Type
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

            # Font & Color
            font_match = re.search(r"Choose Your Font:\s*([^\n]+)", raw)
            towel['Font'] = font_match.group(1).strip() if font_match else ""

            color_match = re.search(r"Font Color:\s*([^\(#\n]+)", raw)
            towel['Font Color'] = color_match.group(1).strip() if color_match else ""

            # Custom Texts
            for t in ['Washcloth', 'Hand Towel', 'Bath Towel']:
                match = re.search(rf"{t}:\s*(.+)", raw)
                towel[f'{t} Text'] = match.group(1).strip() if match else ""

            towel_orders.append(towel)

        elif re.search(r"blanket|swaddle|beanie|knit hat", raw, re.IGNORECASE):
            blanket = base.copy()

            # Blanket Color
            color_match = re.search(r"Blanket Color:\s*([^\n]+)", raw)
            blanket['Blanket Color'] = color_match.group(1).strip() if color_match else ""

            # Font & Thread
            font_match = re.search(r"Font:\s*([^\n]+)", raw)
            blanket['Font'] = font_match.group(1).strip() if font_match else ""

            thread_match = re.search(r"Thread Color:\s*([^\n]+)", raw)
            blanket['Thread Color'] = thread_match.group(1).strip() if thread_match else ""

            # Embroidered Name
            name_match = re.search(r"Blanket Text:\s*([^\n]+)", raw)
            blanket['Name'] = name_match.group(1).strip() if name_match else ""

            # Knit Hat Add-on
            hat_match = re.search(r"Knit Hat:\s*(Yes|No)", raw, re.IGNORECASE)
            blanket['Knit Hat?'] = hat_match.group(1).strip().capitalize() if hat_match else "No"

            # Gift Box — override to Yes if gift note exists
            giftbox_match = re.search(r"Gift Box:\s*(Yes|No)", raw, re.IGNORECASE)
            if gift_note:
                blanket['Gift Box?'] = "Yes"
            else:
                blanket['Gift Box?'] = giftbox_match.group(1).strip().capitalize() if giftbox_match else "No"

            blanket_orders.append(blanket)

    return pd.DataFrame(towel_orders), pd.DataFrame(blanket_orders)


# --- Streamlit App ---
st.set_page_config(page_title="Amazon Orders Split", layout="wide")
st.title("📦 Amazon Custom Orders Split: Towels & Blankets")

uploaded_file = st.file_uploader("Upload a combined Amazon PDF (towels + blankets)", type="pdf")

if uploaded_file:
    towels_df, blankets_df = extract_orders_from_pdf(uploaded_file)

    if not towels_df.empty:
        st.subheader("🧺 Towel Orders")
        st.dataframe(towels_df, use_container_width=True)

    if not blankets_df.empty:
        st.subheader("🍼 Blanket Orders")
        st.dataframe(blankets_df, use_container_width=True)

    # Download Excel with two sheets
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        if not towels_df.empty:
            towels_df.to_excel(writer, sheet_name='Towels', index=False)
        if not blankets_df.empty:
            blankets_df.to_excel(writer, sheet_name='Blankets', index=False)
    excel_buffer.seek(0)

    st.download_button("📥 Download Excel (2 sheets)", excel_buffer, file_name="Amazon_Orders_Towels_and_Blankets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if st.button("🔄 Clear All"):
        st.experimental_rerun()
