import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

def extract_orders_from_pdf(pdf_file):
    orders = []
    with pdfplumber.open(pdf_file) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    raw_orders = text.split("Shipping Address:")[1:]

    for raw in raw_orders:
        order = {}

        # Name and address
        address_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", raw)
        if address_match:
            order['Buyer Name'] = address_match.group(1).strip()
            order['Address'] = f"{address_match.group(2).strip()}, {address_match.group(3).strip()}"

        # Order Date
        date_match = re.search(r"Order Date:\s*(\w{3},\s\w{3}\s\d{1,2},\s\d{4})", raw)
        order['Order Date'] = date_match.group(1) if date_match else ""

        # Order ID
        order_id_match = re.search(r"Order ID:\s*(\d{3}-\d{7}-\d{7})", raw)
        order['Order ID'] = order_id_match.group(1) if order_id_match else ""

        # SKU
        sku_match = re.search(r"SKU:\s*(.+?)\n", raw)
        order['SKU'] = sku_match.group(1).strip() if sku_match else ""

        # Set Type (from SKU or description)
        if "2Pcs" in raw:
            order['Set Type'] = "2pc"
        elif "3Pcs" in raw:
            order['Set Type'] = "3pc"
        elif "6Pcs" in raw:
            order['Set Type'] = "6pc"
        elif "Hand Towel" in raw:
            order['Set Type'] = "Hand"
        else:
            order['Set Type'] = ""

        # Quantity
        qty_match = re.search(r"\bQuantity\s*(\d+)", raw)
        if not qty_match:
            qty_match = re.search(r"^(\d+)\s+Personalized|Monogrammed", raw, re.MULTILINE)
        order['Qty'] = qty_match.group(1) if qty_match else "1"

        # Font
        font_match = re.search(r"Choose Your Font:\s*([^\n]+)", raw)
        order['Font'] = font_match.group(1).strip() if font_match else ""

        # Font Color (just color name)
        color_match = re.search(r"Font Color:\s*([^\(#\n]+)", raw)
        order['Font Color'] = color_match.group(1).strip() if color_match else ""

        # Washcloth
        wash_match = re.search(r"Washcloth:\s*(.+)", raw)
        order['Washcloth Text'] = wash_match.group(1).strip() if wash_match else ""

        # Hand Towel
        hand_match = re.search(r"Hand Towel:\s*(.+)", raw)
        order['Hand Towel Text'] = hand_match.group(1).strip() if hand_match else ""

        # Bath Towel
        bath_match = re.findall(r"Bath Towel:\s*(.+)", raw)
        if bath_match:
            order['Bath Towel Text'] = ', '.join([b.strip() for b in bath_match])
        else:
            order['Bath Towel Text'] = ""

        # Order Item ID
        item_id_match = re.search(r"Order Item ID:\s*(\d+)", raw)
        order['Order Item ID'] = item_id_match.group(1) if item_id_match else ""

        orders.append(order)

    return pd.DataFrame(orders)

st.set_page_config(page_title="Amazon Towel Orders", layout="wide")
st.title("🧺 Embroidery Order Summary (Amazon PDF)")

uploaded_file = st.file_uploader("Upload your Amazon Order PDF", type="pdf")

if uploaded_file is not None:
    df = extract_orders_from_pdf(uploaded_file)
    st.success(f"✅ {len(df)} order(s) extracted!")

    st.write("### 📋 Order Preview")
    st.dataframe(df, use_container_width=True)

    # Excel Download
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    st.download_button("📥 Download Excel", buffer, file_name="Amazon_Towel_Orders.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Clear All Button
    if st.button("🔄 Clear All"):
        st.experimental_rerun()
