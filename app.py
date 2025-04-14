import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

# ==================== DATA EXTRACTION ====================
def extract_orders_from_pdfs(pdf_files):
    all_orders = []

    for pdf_file in pdf_files:
        with pdfplumber.open(pdf_file) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        raw_orders = text.split("Shipping Address:")[1:]

        for raw in raw_orders:
            order = {}

            # Buyer Name
            buyer_match = re.search(r"Buyer Name:\s*(.+)", raw)
            if buyer_match:
                order['Buyer Name'] = buyer_match.group(1).strip()
            else:
                lines = raw.strip().splitlines()
                order['Buyer Name'] = lines[0].strip() if lines else "Unknown"

            # Address
            addr_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", raw)
            if addr_match:
                order['Address'] = f"{addr_match.group(2).strip()}, {addr_match.group(3).strip()}"
            else:
                order['Address'] = ""

            # Order ID
            order_id = re.search(r"Order ID:\s*(\d{3}-\d{7}-\d{7})", raw)
            order['Order ID'] = order_id.group(1).strip() if order_id else ""

            # Order Date
            order_date = re.search(r"Order Date:\s*(.+)", raw)
            order['Order Date'] = order_date.group(1).strip() if order_date else ""

            # Ship Method
            ship_method = re.search(r"Shipping Service:\s*(.+)", raw)
            method = ship_method.group(1).strip() if ship_method else ""
            order['Ship Method'] = "Standard" if "Standard" in method else "Same Day"

            # SKU
            sku = re.search(r"SKU:\s*(.+?)\n", raw)
            order['SKU'] = sku.group(1).strip() if sku else ""

            # Quantity
            quantity = re.search(r"Quantity\s*(\d+)", raw)
            order['Quantity'] = int(quantity.group(1)) if quantity else 1

            # Font + Font Color
            font = re.search(r"Choose Your Font:\s*(.+)", raw)
            order['Font'] = font.group(1).strip() if font else ""
            color = re.search(r"Font Color:\s*([^(\n#]+)", raw)
            order['Font Color'] = color.group(1).strip() if color else ""

            # Product Type
            if "towel" in raw.lower():
                order['Product Type'] = "Towel"
            elif "blanket" in raw.lower():
                order['Product Type'] = "Blanket"
            else:
                order['Product Type'] = "Other"

            # Customization Fields by SKU
            sku_val = order['SKU'].lower()
            if "set-6pcs" in sku_val:
                order['Washcloth 1 Text'] = extract_text(raw, "First Washcloth")
                order['Washcloth 2 Text'] = extract_text(raw, "Second Washcloth")
                order['Hand Towel 1 Text'] = extract_text(raw, "First Hand Towel")
                order['Hand Towel 2 Text'] = extract_text(raw, "Second Hand Towel")
                order['Bath Towel 1 Text'] = extract_text(raw, "First Bath Towel")
                order['Bath Towel 2 Text'] = extract_text(raw, "Second Bath Towel")
            elif "set-3pcs" in sku_val:
                order['Washcloth Text'] = extract_text(raw, "Washcloth")
                order['Hand Towel Text'] = extract_text(raw, "Hand Towel")
                order['Bath Towel Text'] = extract_text(raw, "Bath Towel")
            elif "2pcs" in sku_val:
                order['Towel 1 Text'] = extract_text(raw, "Towel 1")
                order['Towel 2 Text'] = extract_text(raw, "Towel 2")
            elif "ht" in sku_val or "bt" in sku_val or "bs" in sku_val:
                order['Towel Text'] = extract_text(raw, "Towel")

            all_orders.append(order)

    return pd.DataFrame(all_orders)

def extract_text(text, label):
    match = re.search(rf"{label}:\s*(.+)", text)
    return match.group(1).strip() if match else ""

# ==================== STREAMLIT APP ====================
st.set_page_config(page_title="Grouped Towel Orders", layout="wide")
st.title("📦 Grouped Towel Orders by SKU and Buyer")

uploaded_files = st.file_uploader("Upload Amazon Order PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df = extract_orders_from_pdfs(uploaded_files)

    if not df.empty:
        sku_groups = df.groupby("SKU")
        for sku, sku_df in sku_groups:
            st.subheader(f"🧺 SKU: {sku}")
            buyer_groups = sku_df.groupby("Buyer Name")
            for buyer, buyer_df in buyer_groups:
                st.markdown(f"#### 👤 {buyer}")
                st.dataframe(buyer_df.reset_index(drop=True), use_container_width=True)

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='All Orders', index=False)
        excel_buffer.seek(0)
        st.download_button("📥 Download Full Excel", data=excel_buffer, file_name="Grouped_Towel_Orders.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
