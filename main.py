import streamlit as st
import pandas as pd
from PIL import Image
import json
import io
from google import genai
from google.genai import types

# ----------------- 1. PAGE SETUP & MODERN STYLING -----------------
st.set_page_config(
    page_title="LedgerFlow Pro - AI Bookkeeping Dashboard",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom modern CSS for sticky split-view, cards, and audit alerts
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Sticky photo container */
    .sticky-container {
        position: -webkit-sticky;
        position: sticky;
        top: 15px;
        max-height: 88vh;
        overflow-y: auto;
        padding-right: 8px;
    }
    
    /* Modern KPI Cards */
    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin-top: 4px;
        color: #ffffff;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #a0a0a0;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    
    /* Header Badge */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        background: rgba(33, 150, 243, 0.15);
        color: #64b5f6;
        border: 1px solid rgba(33, 150, 243, 0.3);
        margin-bottom: 8px;
    }

    /* Math Audit Alerts */
    .audit-box-green {
        background: rgba(46, 125, 50, 0.15);
        border-left: 4px solid #4caf50;
        border-radius: 6px;
        padding: 8px 12px;
        color: #a5d6a7;
        font-size: 0.88rem;
        margin-bottom: 6px;
    }
    .audit-box-red {
        background: rgba(211, 47, 47, 0.15);
        border-left: 4px solid #f44336;
        border-radius: 6px;
        padding: 8px 12px;
        color: #ef9a9a;
        font-size: 0.88rem;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- 2. API KEY SETUP -----------------
API_KEY = "AQ.Ab8RN6IpNuwu_-WmmHDD-IK3T6cDfA_ebYRNEaAdulNOTyukYA"

try:
    if not API_KEY or API_KEY.startswith("PASTE"):
        API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# ----------------- 3. SIDEBAR CONTROLS -----------------
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    selected_model = st.selectbox(
        "Vision Model",
        options=["gemini-3.6-flash", "gemini-3.5-flash-lite"],
        index=0,
        help="gemini-3.6-flash is the fastest and most accurate for document extraction"
    )
    
    st.markdown("---")
    with st.expander("💡 Photography Tips", expanded=False):
        st.markdown("""
        - **Keep pages flat** to minimize curvature distortion.
        - **Avoid harsh shadows or reflections** over amounts.
        - **Ensure headers & totals** are completely in frame.
        """)

# ----------------- 4. APP HEADER & STATE -----------------
st.markdown('<span class="badge">LEDGERFLOW PRO WORKSTATION</span>', unsafe_allow_html=True)
st.title("📒 Smart Ledger to Excel Dashboard")
st.caption("AI handwriting extraction, side-by-side verification, automated math auditing, and master file sync.")

TARGET_COLUMNS = ["Date", "ID", "Notes", "Amount 1", "USD Rate", "Rate Conv.", "Amount 2"]

if "extracted_df" not in st.session_state or list(st.session_state["extracted_df"].columns) != TARGET_COLUMNS:
    st.session_state["extracted_df"] = pd.DataFrame(columns=TARGET_COLUMNS)

if "stored_images" not in st.session_state:
    st.session_state["stored_images"] = {}

# ----------------- 5. EXTRACTION ENGINE -----------------
def extract_single_image(image_obj, client, model_name):
    prompt = """
    Analyze this handwritten ledger notebook page carefully.
    Extract every row into a structured list of records.
    
    Extract ONLY these fields for each row:
    - Date: date string (e.g. '28-9-2026')
    - ID: bill / invoice number (e.g. '546471')
    - Notes: handwritten notes or car fees (e.g. '车钱 700', '水果 康街做 车钱 1500')
    - Amount 1: first numeric amount column (float or integer)
    - USD Rate: unit or conversion rate if present (e.g. 38.50)
    - Rate Conv.: rate division result if present (e.g. 862.31)
    - Amount 2: second numeric amount column (float or integer)

    For subtotal / total rows: leave ID empty and put 'Subtotal' in Notes.
    Return ONLY valid JSON matching this schema:
    {
      "records": [
        {
          "Date": "28-9-2026",
          "ID": "546471",
          "Notes": "车钱 700",
          "Amount 1": 4208,
          "USD Rate": 38.50,
          "Rate Conv.": null,
          "Amount 2": 4560
        }
      ]
    }
    """
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt, image_obj],
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    parsed = json.loads(response.text)
    return parsed.get("records", [])

# ----------------- 6. INPUT MODES (BATCH QUEUE / LIVE / MERGE) -----------------
input_tab1, input_tab2, input_tab3 = st.tabs([
    "📁 Upload Pages (Batch Queue)", 
    "📸 Live Camera Snapshot", 
    "📂 Append to Master Excel File"
])

new_images_to_process = []

with input_tab1:
    files = st.file_uploader(
        "Upload 1 or multiple ledger photos (Hold Ctrl/Cmd to select multiple)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="batch_uploader"
    )
    if files:
        for f in files:
            new_images_to_process.append((f.name, Image.open(f)))

with input_tab2:
    cam = st.camera_input("Snap a ledger page from your camera", key="cam_shot")
    if cam:
        new_images_to_process.append(("Camera_Shot.png", Image.open(cam)))

with input_tab3:
    st.write("Upload your existing `master_ledger.xlsx` to add new scanned records to it.")
    existing_excel = st.file_uploader("Upload Existing Master File", type=["xlsx", "xls"], key="merge_excel")
    if existing_excel:
        if st.button("📥 Merge Master File Into Table"):
            try:
                uploaded_df = pd.read_excel(existing_excel)
                # Normalize column headers
                col_map = {
                    "Amount 1 ($)": "Amount 1",
                    "Amount 2 ($)": "Amount 2",
                    "Rate Conv. ($)": "Rate Conv."
                }
                uploaded_df = uploaded_df.rename(columns=col_map)
                
                for c in TARGET_COLUMNS:
                    if c not in uploaded_df.columns:
                        uploaded_df[c] = None
                uploaded_df = uploaded_df[TARGET_COLUMNS].fillna("")
                
                st.session_state["extracted_df"] = pd.concat(
                    [st.session_state["extracted_df"], uploaded_df],
                    ignore_index=True
                ).drop_duplicates()
                st.success(f"Merged {len(uploaded_df)} records from existing file!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to merge Excel: {e}")

# Process Batch Button
if new_images_to_process:
    st.markdown("---")
    c_btn, c_info = st.columns([1, 3])
    with c_btn:
        start_process = st.button(
            f"🚀 Extract {len(new_images_to_process)} Page(s)",
            type="primary",
            use_container_width=True
        )
    with c_info:
        st.caption(f"{len(new_images_to_process)} image(s) queued for extraction.")

    if start_process:
        if not API_KEY or API_KEY.startswith("PASTE"):
            st.error("Please configure your Gemini API Key in line 50 of main.py.")
        else:
            client = genai.Client(api_key=API_KEY)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_added = 0
            for idx, (img_name, img_data) in enumerate(new_images_to_process):
                status_text.text(f"Extracting Page {idx+1} of {len(new_images_to_process)}: {img_name}...")
                try:
                    recs = extract_single_image(img_data, client, selected_model)
                    if recs:
                        df_page = pd.DataFrame(recs)
                        for col in TARGET_COLUMNS:
                            if col not in df_page.columns:
                                df_page[col] = None
                        df_page = df_page[TARGET_COLUMNS]
                        df_page["ID"] = df_page["ID"].fillna("")
                        df_page["Notes"] = df_page["Notes"].fillna("")
                        df_page["Date"] = df_page["Date"].fillna("")
                        
                        st.session_state["extracted_df"] = pd.concat(
                            [st.session_state["extracted_df"], df_page],
                            ignore_index=True
                        )
                        st.session_state["stored_images"][img_name] = img_data
                        total_added += len(recs)
                except Exception as e:
                    st.error(f"Error on {img_name}: {e}")
                
                progress_bar.progress((idx + 1) / len(new_images_to_process))

            status_text.success(f"Batch complete! Added {total_added} total rows.")
            st.rerun()

# ----------------- 7. DASHBOARD & SIDE-BY-SIDE VERIFICATION -----------------
df = st.session_state["extracted_df"]

if not df.empty:
    st.markdown("---")
    
    # Summary KPI Cards (formatted with $)
    is_subtotal = df["Notes"].astype(str).str.contains("Subtotal", case=False, na=False)
    regular_rows = df[~is_subtotal]
    
    sum_amt_1 = pd.to_numeric(regular_rows["Amount 1"], errors="coerce").sum()
    sum_amt_2 = pd.to_numeric(regular_rows["Amount 2"], errors="coerce").sum()
    unique_dates = df["Date"].replace("", None).dropna().nunique()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Entries</div><div class="metric-value">{len(regular_rows)}</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Sum Amount 1</div><div class="metric-value">${sum_amt_1:,.2f}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Sum Amount 2</div><div class="metric-value">${sum_amt_2:,.2f}</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Dates Logged</div><div class="metric-value">{unique_dates}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------- 8. AUTOMATED MATH AUDIT ENGINE -----------------
    st.markdown("#### 🔍 Automated Mathematical Audit & Discrepancy Warnings")
    
    dates_in_df = [d for d in df["Date"].unique() if d]
    audit_results = []
    
    for d in dates_in_df:
        day_df = df[df["Date"] == d]
        day_items = day_df[~day_df["Notes"].astype(str).str.contains("Subtotal", case=False, na=False)]
        day_subtotals = day_df[day_df["Notes"].astype(str).str.contains("Subtotal", case=False, na=False)]
        
        calc_amt_1 = pd.to_numeric(day_items["Amount 1"], errors="coerce").sum()
        calc_amt_2 = pd.to_numeric(day_items["Amount 2"], errors="coerce").sum()
        
        if not day_subtotals.empty:
            rep_amt_1 = pd.to_numeric(day_subtotals.iloc[0]["Amount 1"], errors="coerce")
            rep_amt_2 = pd.to_numeric(day_subtotals.iloc[0]["Amount 2"], errors="coerce")
            rate_val = pd.to_numeric(day_subtotals.iloc[0]["USD Rate"], errors="coerce")
            rep_conv = pd.to_numeric(day_subtotals.iloc[0]["Rate Conv."], errors="coerce")

            # Check Amount 1 sum
            diff1 = abs(calc_amt_1 - rep_amt_1) if pd.notnull(rep_amt_1) else 0
            if diff1 < 0.05:
                audit_results.append((True, f"🟢 **{d}**: Math verified! Sum of Amount 1 (${calc_amt_1:,.2f}) matches ledger Subtotal (${rep_amt_1:,.2f}) perfectly."))
            else:
                audit_results.append((False, f"🔴 **{d} Discrepancy**: Calculated sum of Amount 1 is **${calc_amt_1:,.2f}**, but Subtotal is written as **${rep_amt_1:,.2f}** (Difference: ${diff1:,.2f}). Please verify rows."))

            # Check Rate Conversion calculation
            if pd.notnull(rate_val) and rate_val > 0 and pd.notnull(rep_conv) and pd.notnull(rep_amt_1):
                calc_conv = rep_amt_1 / rate_val
                if abs(calc_conv - rep_conv) < 0.1:
                    audit_results.append((True, f"🟢 **{d}**: Rate conversion (${rep_amt_1:,.2f} ÷ {rate_val} = ${rep_conv:,.2f}) is mathematically verified."))
                else:
                    audit_results.append((False, f"🔴 **{d} Rate Alert**: ${rep_amt_1:,.2f} ÷ {rate_val} computes to ${calc_conv:,.2f}, but ledger shows ${rep_conv:,.2f}."))

    if audit_results:
        with st.expander(f"Audit Summary ({len(audit_results)} checks evaluated)", expanded=True):
            for is_ok, msg in audit_results:
                if is_ok:
                    st.markdown(f'<div class="audit-box-green">{msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="audit-box-red">{msg}</div>', unsafe_allow_html=True)

    # ----------------- 9. SIDE-BY-SIDE SPLIT VIEW -----------------
    st.markdown("---")
    
    col_split_img, col_split_data = st.columns([1, 1.4], gap="large")

    # LEFT: Sticky Image Inspector with Zoom Controls
    with col_split_img:
        st.markdown('<div class="sticky-container">', unsafe_allow_html=True)
        st.subheader("🖼️ Sticky Image Inspector")
        
        if st.session_state["stored_images"]:
            img_choice = st.selectbox(
                "Select page to inspect:",
                options=list(st.session_state["stored_images"].keys())
            )
            
            # Zoom slider for checking messy handwriting
            zoom_pct = st.slider("🔍 Zoom Image", min_value=50, max_value=250, value=100, step=10)
            
            selected_image = st.session_state["stored_images"][img_choice]
            new_width = int(selected_image.width * (zoom_pct / 100.0))
            new_height = int(selected_image.height * (zoom_pct / 100.0))
            zoomed_img = selected_image.resize((new_width, new_height))
            
            st.image(zoomed_img, caption=f"{img_choice} ({zoom_pct}%)", use_container_width=True)
        else:
            st.info("Upload photos above to view them here side-by-side with your table.")
        
        st.markdown('</div>', unsafe_allow_html=True)

    # RIGHT: Filter Bar + Table + Subtotal Highlighting + Reset
    with col_split_data:
        h_col, b_col = st.columns([3, 1])
        with h_col:
            st.subheader("📋 Master Table")
        with b_col:
            if st.button("🗑️ Clear / Reset", use_container_width=True):
                st.session_state["extracted_df"] = pd.DataFrame(columns=TARGET_COLUMNS)
                st.session_state["stored_images"] = {}
                st.rerun()

        # Dynamic Search & Filter Bar
        st.markdown("##### 🔎 Quick Search & Filter")
        f1, f2, f3 = st.columns([1, 1, 1])
        with f1:
            date_filter = st.selectbox("Date", options=["All"] + dates_in_df)
        with f2:
            id_search = st.text_input("Bill ID", "")
        with f3:
            notes_search = st.text_input("Notes Keyword (e.g. 车钱)", "")

        filtered_df = df.copy()
        if date_filter != "All":
            filtered_df = filtered_df[filtered_df["Date"] == date_filter]
        if id_search:
            filtered_df = filtered_df[filtered_df["ID"].astype(str).str.contains(id_search, case=False, na=False)]
        if notes_search:
            filtered_df = filtered_df[filtered_df["Notes"].astype(str).str.contains(notes_search, case=False, na=False)]

        st.caption(f"Showing **{len(filtered_df)}** of **{len(df)}** rows. (Subtotal rows are marked in **bold**).")

        # ----------------- 10. EDITABLE TABLE WITH DOLLAR FORMATTING -----------------
        edited_df = st.data_editor(
            filtered_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Date": st.column_config.TextColumn("Date"),
                "ID": st.column_config.TextColumn("ID"),
                "Notes": st.column_config.TextColumn("Notes"),
                "Amount 1": st.column_config.NumberColumn("Amount 1 ($)", format="$%.2f"),
                "USD Rate": st.column_config.NumberColumn("USD Rate", format="%.2f"),
                "Rate Conv.": st.column_config.NumberColumn("Rate Conv. ($)", format="$%.2f"),
                "Amount 2": st.column_config.NumberColumn("Amount 2 ($)", format="$%.2f")
            }
        )

        # ----------------- 11. EXPORT CENTER -----------------
        st.markdown("#### 📥 Export Clean Master File")
        exp1, exp2 = st.columns(2)
        
        # Prepare clean display columns with $ in headers for Excel & CSV
        export_df = edited_df.rename(columns={
            "Amount 1": "Amount 1 ($)",
            "Amount 2": "Amount 2 ($)",
            "Rate Conv.": "Rate Conv. ($)"
        })

        with exp1:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Master_Ledger')
            
            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name="master_ledger.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with exp2:
            csv_data = export_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📄 Download CSV (.csv)",
                data=csv_data,
                file_name="master_ledger.csv",
                mime="text/csv",
                use_container_width=True
            )
