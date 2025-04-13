import streamlit as st
import PyPDF2
import re
import pandas as pd
from fpdf import FPDF
import io
import base64
from datetime import datetime

# Constants
LABEL_WIDTH = 4 * 25.4  # 4 inches in mm
LABEL_HEIGHT = 6 * 25.4  # 6 inches in mm
FONT_SIZE = 10
LINE_HEIGHT = 5

def extract_orders_from_pdfs(pdf_files):
    """
    Extract order information from Amazon PDF exports using regex patterns.
    Returns a dictionary with towel and blanket orders.
    """
    orders = {'towels': [], 'blankets': []}
    
    # Improved regex patterns based on the sample files
    order_id_pattern = r'Order ID:\s*(\d+-\d+-\d+)'
    buyer_pattern = r'Ship to:\s*(.+?)\n|# (.+?)\n'
    address_pattern = r'Ship to:.+?\n(.+?)\n\n|# .+?\n(.+?)\n'
    product_pattern = r'(\d+)\s*of\s*(.+?)\n(.+?)\n(.+?)\n|Quantity\s*Product Details\s*Unit price\s*Order Totals\s*\d+\s*(.+?)\n(.+?)\n(.+?)\n'
    customization_pattern = r'Customizations?:?\s*(.+?)(?:\n\n|\nShipping Address|\nReturning your|$)'
    gift_note_pattern = r'Gift [mM]essage:\s*(.+?)(?:\n\n|\nShipping Address|\nReturning your|$)'
    
    for pdf_file in pdf_files:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        for page in pdf_reader.pages:
            text = page.extract_text()
            
            # Extract basic order info
            order_id_match = re.search(order_id_pattern, text)
            buyer_match = re.search(buyer_pattern, text)
            address_match = re.search(address_pattern, text, re.DOTALL)
            
            if not (order_id_match and buyer_match and address_match):
                continue
                
            order_id = order_id_match.group(1)
            buyer = buyer_match.group(1) or buyer_match.group(2)
            buyer = buyer.strip()
            
            # Clean up address
            address = address_match.group(1) or address_match.group(2)
            address = address.strip().replace('\n', ', ')
            
            # Extract product details - improved to handle different formats
            product_matches = re.finditer(product_pattern, text, re.DOTALL)
            
            for match in product_matches:
                if match.group(1):  # First pattern matched
                    quantity = match.group(1)
                    product_title = match.group(2).strip()
                    sku = match.group(3).strip()
                    fnsku = match.group(4).strip()
                else:  # Second pattern matched
                    quantity = "1"
                    product_title = match.group(5).strip()
                    sku = match.group(6).strip()
                    fnsku = match.group(7).strip() if match.group(7) else ""
                
                # Extract customization
                customization_match = re.search(customization_pattern, text[match.end():], re.DOTALL)
                customization = customization_match.group(1).strip() if customization_match else ""
                
                # Extract gift note
                gift_note_match = re.search(gift_note_pattern, text, re.DOTALL)
                gift_note = gift_note_match.group(1).strip() if gift_note_match else ""
                
                # Parse customization details based on product type
                if 'towel' in product_title.lower() or 'washcloth' in product_title.lower():
                    # Parse towel customization
                    towel_details = parse_towel_customization(customization)
                    order_data = {
                        'order_id': order_id,
                        'buyer': buyer,
                        'address': address,
                        'product_title': product_title,
                        'sku': sku,
                        'fnsku': fnsku,
                        'quantity': quantity,
                        **towel_details,
                        'gift_note': gift_note
                    }
                    orders['towels'].append(order_data)
                elif 'blanket' in product_title.lower():
                    # Parse blanket customization
                    blanket_details = parse_blanket_customization(customization)
                    order_data = {
                        'order_id': order_id,
                        'buyer': buyer,
                        'address': address,
                        'product_title': product_title,
                        'sku': sku,
                        'fnsku': fnsku,
                        'quantity': quantity,
                        **blanket_details,
                        'gift_note': gift_note
                    }
                    orders['blankets'].append(order_data)
    
    return orders

def parse_towel_customization(customization_text):
    """Parse towel customization details from text"""
    details = {
        'font': '',
        'font_color': '',
        'washcloth_text': '',
        'hand_text': '',
        'bath_text': ''
    }
    
    if not customization_text:
        return details
    
    # Improved parsing for towel customizations
    font_match = re.search(r'(?:Font|Choose Your Font):\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if font_match:
        details['font'] = font_match.group(1).strip()
    
    color_match = re.search(r'(?:Font Color|Thread Color):\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if color_match:
        details['font_color'] = color_match.group(1).strip()
    
    wash_match = re.search(r'(?:Washcloth|First Washcloth):\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if wash_match:
        details['washcloth_text'] = wash_match.group(1).strip()
    
    hand_match = re.search(r'(?:Hand Towel|First Hand Towel):\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if hand_match:
        details['hand_text'] = hand_match.group(1).strip()
    
    bath_match = re.search(r'(?:Bath Towel|First Bath Towel):\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if bath_match:
        details['bath_text'] = bath_match.group(1).strip()
    
    return details

def parse_blanket_customization(customization_text):
    """Parse blanket customization details from text"""
    details = {
        'font': '',
        'thread_color': '',
        'name': '',
        'blanket_color': '',
        'gift_box': False,
        'knit_hat': False
    }
    
    if not customization_text:
        return details
    
    # Improved parsing for blanket customizations
    color_match = re.search(r'Blanket Color:\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if color_match:
        details['blanket_color'] = color_match.group(1).strip()
    
    font_match = re.search(r'Embroidery Font:\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if font_match:
        details['font'] = font_match.group(1).strip()
    
    thread_match = re.search(r'Thread Color:\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if thread_match:
        details['thread_color'] = thread_match.group(1).strip()
    
    name_match = re.search(r'Name:\s*(.+?)(?:;|\n|$)', customization_text, re.IGNORECASE)
    if name_match:
        details['name'] = name_match.group(1).strip()
    
    hat_match = re.search(r'Add Customized Knit Hat:\s*(Yes Please|No Thank You)', customization_text, re.IGNORECASE)
    if hat_match:
        details['knit_hat'] = hat_match.group(1).strip().lower() == 'yes please'
    
    box_match = re.search(r'Gift Box & Message:\s*(Yes Please!|No, Thank you)', customization_text, re.IGNORECASE)
    if box_match:
        details['gift_box'] = box_match.group(1).strip().lower() == 'yes please!'
    
    return details

def create_4x6_labels(orders):
    """Generate printable 4x6 PDF labels for the orders"""
    pdf = FPDF(orientation='P', unit='mm', format=(LABEL_WIDTH, LABEL_HEIGHT))
    pdf.set_margins(5, 5, 5)  # Small margins
    pdf.set_auto_page_break(False)
    
    # Group items by order ID
    combined_orders = {}
    for order_type in orders:
        for order in orders[order_type]:
            order_id = order['order_id']
            if order_id not in combined_orders:
                combined_orders[order_id] = {
                    'buyer': order['buyer'],
                    'address': order['address'],
                    'items': [],
                    'gift_note': order.get('gift_note', '')
                }
            combined_orders[order_id]['items'].append(order)
    
    # Create a label for each order
    for order_id, order_data in combined_orders.items():
        pdf.add_page()
        pdf.set_font('Arial', 'B', FONT_SIZE)
        pdf.cell(0, LINE_HEIGHT, f"Order ID: {order_id}", ln=1)
        pdf.set_font('Arial', '', FONT_SIZE)
        pdf.cell(0, LINE_HEIGHT, f"Buyer: {order_data['buyer']}", ln=1)
        
        # Handle address with proper line breaks
        address_lines = order_data['address'].split(', ')
        for line in address_lines:
            pdf.cell(0, LINE_HEIGHT, line, ln=1)
        
        pdf.ln(2)
        
        # Add items
        for item in order_data['items']:
            pdf.set_font('Arial', 'B', FONT_SIZE)
            pdf.cell(0, LINE_HEIGHT, f"Product: {item['product_title']}", ln=1)
            pdf.set_font('Arial', '', FONT_SIZE)
            pdf.cell(0, LINE_HEIGHT, f"SKU: {item['sku']}", ln=1)
            pdf.cell(0, LINE_HEIGHT, f"FNSKU: {item.get('fnsku', '')}", ln=1)
            pdf.cell(0, LINE_HEIGHT, f"Qty: {item['quantity']}", ln=1)
            
            # Add customization details based on product type
            if 'towel' in item['product_title'].lower():
                pdf.cell(0, LINE_HEIGHT, f"Font: {item.get('font', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Font Color: {item.get('font_color', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Washcloth: {item.get('washcloth_text', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Hand Towel: {item.get('hand_text', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Bath Towel: {item.get('bath_text', '')}", ln=1)
            elif 'blanket' in item['product_title'].lower():
                pdf.cell(0, LINE_HEIGHT, f"Blanket Color: {item.get('blanket_color', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Font: {item.get('font', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Thread Color: {item.get('thread_color', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Name: {item.get('name', '')}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Knit Hat: {'Yes' if item.get('knit_hat', False) else 'No'}", ln=1)
                pdf.cell(0, LINE_HEIGHT, f"Gift Box: {'Yes' if item.get('gift_box', False) else 'No'}", ln=1)
            
            pdf.ln(2)
        
        # Add gift note if present
        if order_data['gift_note']:
            pdf.set_font('Arial', 'B', FONT_SIZE)
            pdf.cell(0, LINE_HEIGHT, "Gift Note:", ln=1)
            pdf.set_font('Arial', '', FONT_SIZE)
            
            # Handle long gift notes with text wrapping
            gift_note = order_data['gift_note']
            max_width = LABEL_WIDTH - 10  # Account for margins
            max_chars_per_line = int(max_width / (FONT_SIZE * 0.5))  # Approximate chars per line
            
            for i in range(0, len(gift_note), max_chars_per_line):
                pdf.cell(0, LINE_HEIGHT, gift_note[i:i+max_chars_per_line], ln=1)
    
    return pdf

def get_table_download_link(df, filename, link_text):
    """Generates a link to download the dataframe as a CSV or Excel file"""
    output = io.BytesIO()
    
    if filename.endswith('.csv'):
        df.to_csv(output, index=False)
        mime = 'text/csv'
    else:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:{mime};base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def main():
    st.title("Custom Embroidery Order Processor")
    st.write("Upload Amazon order PDFs to extract order details and generate labels")
    
    # File upload
    uploaded_files = st.file_uploader("Upload Amazon Order PDFs", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        # Process files
        orders = extract_orders_from_pdfs(uploaded_files)
        
        # Create dataframes
        df_towels = pd.DataFrame(orders['towels'])
        df_blankets = pd.DataFrame(orders['blankets'])
        
        # Display download buttons at the top
        st.markdown("### Download Order Data")
        col1, col2 = st.columns(2)
        with col1:
            if not df_towels.empty:
                st.markdown(get_table_download_link(df_towels, 'towel_orders.csv', 'Download Towel Orders (CSV)'), unsafe_allow_html=True)
                st.markdown(get_table_download_link(df_towels, 'towel_orders.xlsx', 'Download Towel Orders (Excel)'), unsafe_allow_html=True)
        with col2:
            if not df_blankets.empty:
                st.markdown(get_table_download_link(df_blankets, 'blanket_orders.csv', 'Download Blanket Orders (CSV)'), unsafe_allow_html=True)
                st.markdown(get_table_download_link(df_blankets, 'blanket_orders.xlsx', 'Download Blanket Orders (Excel)'), unsafe_allow_html=True)
        
        # Generate labels
        if st.button("Generate 4x6 Labels"):
            labels_pdf = create_4x6_labels(orders)
            
            # Save the PDF to a bytes buffer
            pdf_bytes = io.BytesIO()
            labels_pdf.output(pdf_bytes)
            pdf_bytes.seek(0)
            
            # Create download link
            b64 = base64.b64encode(pdf_bytes.read()).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="embroidery_labels.pdf">Download Labels PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
        
        # Display preview tables
        st.markdown("### Towel Orders Preview")
        if not df_towels.empty:
            st.dataframe(df_towels)
        else:
            st.write("No towel orders found")
        
        st.markdown("### Blanket Orders Preview")
        if not df_blankets.empty:
            st.dataframe(df_blankets)
        else:
            st.write("No blanket orders found")

if __name__ == "__main__":
    main()
