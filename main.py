import streamlit as st
import pandas as pd
from PIL import Image
import json
import io
from google import genai
from google.genai import types

st.set_page_config(page_title="Ledger to Excel", layout="wide")

st.title("📒 Handwritten Ledger to Excel Extractor")
st.write("Upload a photo of your handwritten ledger, review the table, and export to Excel.")

# Sidebar for Gemini API Key
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
st.sidebar.markdown("[Get a free Gemini API key here](https://aistudio.google.com/)")

uploaded_file = st.file_uploader("Choose an image or take a photo...", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        img = Image.open(uploaded_file)
        st.image(img, caption="Uploaded Ledger", use_container_width=True)

    with col2:
        if st.button("🚀 Extract Data to Table", type="primary"):
            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar.")
            else:
                with st.spinner("Extracting handwritten text and validating numbers..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        prompt = """
                        Analyze this handwritten ledger notebook page carefully.
                        Extract every row into a structured list of records.
                        
                        Columns to extract:
                        - date: e.g., '28-9-2026'
                        - category: e.g., '水果' (or empty if not specified)
                        - code_or_bill_no: e.g., '546471'
                        - remarks: handwritten notes, car fees (e.g. '车钱 700', '康街做')
                        - amount_1: first numeric column
                        - rate: conversion or unit rate if present (e.g. 38.50)
                        - calculated_rate_amt: rate division result if present (e.g. 862.31)
                        - amount_2: second numeric column
                        
                        Also include subtotal / summary rows with 'is_subtotal': true.
                        Ensure numbers are properly parsed as floats or integers where possible.
                        Return ONLY valid JSON matching this schema:
                        {
                          "records": [
                            {
                              "date": "28-9-2026",
                              "category": "水果",
                              "code_or_bill_no": "546471",
                              "remarks": "车钱 700",
                              "amount_1": 4208,
                              "rate": 38.50,
                              "calculated_rate_amt": null,
                              "amount_2": 4560,
                              "is_subtotal": false
                            }
                          ]
                        }
                        """

                        response = client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=[prompt, img],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )

                        parsed = json.loads(response.text)
                        records = parsed.get("records", [])
                        
                        if records:
                            df = pd.DataFrame(records)
                            st.session_state["extracted_df"] = df
                            st.success("Extraction completed successfully!")
                        else:
                            st.warning("No records found in image.")

                    except Exception as e:
                        st.error(f"Error during extraction: {e}")

        # If data exists in session, display editable table & Excel download
        if "extracted_df" in st.session_state:
            st.subheader("📋 Review & Edit Data")
            st.info("You can edit any cell directly in the table below before exporting.")
            
            # Interactive editable table
            edited_df = st.data_editor(
                st.session_state["extracted_df"],
                use_container_width=True,
                num_rows="dynamic"
            )

            # Export to Excel buffer
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Ledger_Entries')
            
            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name="ledger_extracted.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
