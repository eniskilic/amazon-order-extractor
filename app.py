import streamlit as st
import pdfplumber
import pandas as pd
import re

def extract_orders_from_pdf(pdf_file):
    orders = []
    with pdfplumber.open(pdf_file) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    raw_orders = text.split("Shipping Address:")[1:]

    for raw in raw_orders:
        order = {}

        address_match = re.search(r"([\w\s\.'\-]+)\n(.+?)\n(.+?\d{5}.*?)\n", raw)
        if address_match:
            order['Name'] = address_match.group(1).strip()
            order['Street'] = address_match.group(2).strip()
            order['City/State/ZIP'] = address_match.group(3).strip()

        order_id_match = re.search(r"Order ID:\s*(\d{3}-\d{7}-\d{7})", raw)
        order['Order ID'] = order_id_match.group(1) if order_id_match else ""

        product_match = re.search(r"Product Details\s*(.*?)\s*SKU:", raw, re.DOTALL)
        order['Product'] = product_match.group(1).strip().replace("\n", " ") if product_match else ""

        customization_match = re.search(r"Customizations:\s*(.*?)\$\d+\.\d{2}", raw, re.DOTALL)
        order['Customizations'] = customization_match.group(1).strip().replace("\n", " ") if customization_match else ""

        total_match = re.search(r"Grand total: \$([0-9]+\.[0-9]{2})", raw)
        order['Grand Total ($)'] = total_match.group(1) if total_match else ""

        orders.append(order)

    return pd.DataFrame(orders)

st.title("🧺 Amazon Towel Orders Extractor")
uploaded_file = st.file_uploader("Upload your Amazon order PDF", type="pdf")

if uploaded_file is not None:
    df = extract_orders_from_pdf(uploaded_file)
    st.write("### 📝 Order Details")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name='amazon_orders.csv',
        mime='text/csv',
    )

    st.button("🔄 Clear All", on_click=lambda: st.experimental_rerun())
