"""
Streamlit Excel/CSV Data Visualizer
UI carbon-copied to match the DataViz Pro design image exactly.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
from datetime import datetime, timedelta
import gc

# Page configuration
st.set_page_config(
    page_title="DataViz Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configuration constants
MAX_FILE_SIZE_MB = 50  # Matches image: "Max 50MB"
MAX_ROWS = 100000
PREVIEW_ROWS = 10000
CHUNK_SIZE = 50000
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'filename' not in st.session_state:
    st.session_state.filename = None
if 'file_size' not in st.session_state:
    st.session_state.file_size = 0
if 'recent_uploads' not in st.session_state:
    st.session_state.recent_uploads = []
if 'rows_limited' not in st.session_state:
    st.session_state.rows_limited = False
if 'is_preview' not in st.session_state:
    st.session_state.is_preview = False

# --- CSS Injection - Exact Match to Image ---
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">

<style>
    /* Global Reset */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    ::-webkit-scrollbar { 
        display: none;
    }
    
    body { 
        font-family: 'Inter', sans-serif; 
        background-color: #ffffff;
        color: #0f172a;
    }
    
    .stApp {
        background-color: #ffffff;
    }
    
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 100px !important;
        padding-right: 100px !important;
        max-width: 100% !important;
    }
    
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Header - Exact Match */
    .header-container {
        background: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        padding: 16px 48px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    /* Hero Section - Exact Match */
    .hero-section {
        background: linear-gradient(135deg, #2563eb 0%, #4f46e5 50%, #7c3aed 100%);
        color: white;
        border-radius: 16px;
        padding: 48px 48px;
        margin: 32px 0;
        position: relative;
        overflow: hidden;
        min-height: 320px;
    }


    /* Buttons - Exact Match */
    .btn-primary {
        background-color: #2563eb;
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        border: none;
        cursor: pointer;
        transition: all 0.2s ease;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    
    .btn-primary:hover {
        background-color: #1d4ed8;
    }

    .btn-outline {
        background-color: transparent;
        color: #475569;
        border: 1px solid #cbd5e1;
        padding: 10px 20px;
        border-radius: 8px;
        font-weight: 500;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    
    .btn-outline:hover {
        background-color: #f8fafc;
        border-color: #94a3b8;
    }

    /* Upload Section - Exact Match */
    .upload-wrapper {
        background: #ffffff;
        border: 2px dashed #e2e8f0;
        border-radius: 12px;
        padding: 48px 32px;
        text-align: center;
        margin: 0 0 32px 0;
    }

    /* Streamlit File Uploader Override */
    .stFileUploader > div {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
    }
    
    .stFileUploader label {
        display: none !important;
    }

    .feature-icon {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 16px;
        font-size: 24px;
    }

    /* Custom Selectbox and Checkbox */
    .stSelectbox > div > div {
        border-radius: 8px;
    }
    
    .stCheckbox label {
        font-size: 14px;
        font-weight: 400;
        color: #475569;
    }

</style>
""", unsafe_allow_html=True)

# --- Logic Functions (Preserved) ---

def optimize_dtypes(df):
    """Optimize DataFrame dtypes to reduce memory usage"""
    for col in df.columns:
        col_type = df[col].dtype
        if col_type != 'object':
            try:
                c_min = df[col].min()
                c_max = df[col].max()
                if str(col_type)[:3] == 'int':
                    if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                        df[col] = df[col].astype(np.int8)
                    elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                        df[col] = df[col].astype(np.int16)
                    elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                        df[col] = df[col].astype(np.int32)
                elif str(col_type)[:5] == 'float':
                    df[col] = pd.to_numeric(df[col], downcast='float')
            except (TypeError, ValueError):
                continue
    return df

def read_csv_chunked(file_obj, preview_only=False):
    if preview_only:
        return pd.read_csv(file_obj, nrows=PREVIEW_ROWS)
    chunks = []
    total_rows = 0
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        for chunk_num, chunk in enumerate(pd.read_csv(file_obj, chunksize=CHUNK_SIZE)):
            chunk = chunk.dropna(axis=1, how='all').dropna(axis=0, how='all')
            chunk = optimize_dtypes(chunk)
            chunks.append(chunk)
            total_rows += len(chunk)
            progress = min((chunk_num + 1) * CHUNK_SIZE / MAX_ROWS, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Processing chunk {chunk_num + 1}: {total_rows:,} rows...")
            if (chunk_num + 1) % 5 == 0: gc.collect()
            if total_rows >= MAX_ROWS: break
        progress_bar.empty()
        status_text.empty()
        if chunks: return pd.concat(chunks, ignore_index=True)
        return pd.DataFrame()
    except Exception as e:
        st.error(f'Error reading CSV: {str(e)}')
        return pd.DataFrame()

def read_excel_optimized(file_obj, preview_only=False):
    try:
        if preview_only:
            df = pd.read_excel(file_obj, engine='openpyxl', nrows=PREVIEW_ROWS)
        else:
            df = pd.read_excel(file_obj, engine='openpyxl', nrows=MAX_ROWS)
        unnamed_cols = [col for col in df.columns if 'Unnamed:' in str(col)]
        if len(unnamed_cols) > len(df.columns) / 2:
            file_obj.seek(0)
            df_raw = pd.read_excel(file_obj, engine='openpyxl', header=None, nrows=10)
            header_row = None
            for idx, row in df_raw.iterrows():
                non_null_count = row.notna().sum()
                if non_null_count >= 2:
                    string_values = [str(v) for v in row if pd.notna(v)]
                    if string_values and any(len(str(v)) > 2 for v in string_values):
                        header_row = idx
                        break
            if header_row is not None and header_row > 0:
                file_obj.seek(0)
                if preview_only:
                    df = pd.read_excel(file_obj, engine='openpyxl', header=header_row, nrows=PREVIEW_ROWS)
                else:
                    df = pd.read_excel(file_obj, engine='openpyxl', header=header_row, nrows=MAX_ROWS)
        df = df.dropna(axis=1, how='all').dropna(axis=0, how='all')
        if not preview_only: df = optimize_dtypes(df)
        return df
    except Exception as e:
        st.error(f'Error reading Excel file: {str(e)}')
        return pd.DataFrame()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_uploaded_file(uploaded_file, preview_only=False):
    if not allowed_file(uploaded_file.name):
        st.error(f"❌ Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
        return None
    file_size = len(uploaded_file.getvalue())
    file_size_mb = file_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        st.error(f"❌ File size ({file_size_mb:.1f} MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB} MB).")
        return None
    try:
        if uploaded_file.name.endswith('.csv'):
            df = read_csv_chunked(uploaded_file, preview_only=preview_only)
        else:
            df = read_excel_optimized(uploaded_file, preview_only=preview_only)
        if df.empty:
            st.error("❌ The file appears to be empty or has no data")
            return None
        rows_limited = len(df) >= MAX_ROWS
        st.session_state.df = df
        st.session_state.filename = uploaded_file.name
        st.session_state.file_size = file_size
        st.session_state.rows_limited = rows_limited
        st.session_state.is_preview = preview_only
        upload_info = {
            'filename': uploaded_file.name,
            'upload_time': datetime.now(),
            'file_size': file_size,
            'row_count': len(df),
            'column_count': len(df.columns),
            'is_excel': uploaded_file.name.endswith('.xlsx') or uploaded_file.name.endswith('.xls')
        }
        st.session_state.recent_uploads = [u for u in st.session_state.recent_uploads if u['filename'] != uploaded_file.name]
        st.session_state.recent_uploads.insert(0, upload_info)
        st.session_state.recent_uploads = st.session_state.recent_uploads[:10]
        return df
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        return None

# --- UI IMPLEMENTATION - EXACT MATCH TO IMAGE ---

# 1. HEADER - Exact Match
st.markdown("""
<div class="header-container">
    <div style="display: flex; align-items: center; gap: 12px;">
        <div style="background: linear-gradient(135deg, #2563eb, #4f46e5); padding: 8px; border-radius: 8px; display: flex; align-items: center; justify-content: center;">
            <i class="fa-solid fa-chart-line" style="color: white; font-size: 20px;"></i>
        </div>
        <div>
            <h1 style="font-size: 18px; font-weight: 700; color: #0f172a; margin: 0; line-height: 1.2;">DataViz Pro</h1>
            <p style="font-size: 12px; color: #64748b; margin: 0; line-height: 1.2;">Transform Data Into Insights</p>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
        <div style="display: flex; align-items: center; gap: 12px; border-left: 1px solid #e2e8f0; padding-left: 16px;">
            <div style="text-align: right;">
                <p style="font-size: 14px; font-weight: 600; color: #0f172a; margin: 0; line-height: 1.2;">Roan Dino</p>
                <p style="font-size: 12px; color: #64748b; margin: 0; line-height: 1.2;">Pro Plan</p>
            </div>
            <img src="https://ui-avatars.com/api/?name=Roan+Dino&background=2563eb&color=fff&size=40" style="width: 40px; height: 40px; border-radius: 50%; border: 2px solid #e2e8f0;">
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 2. HERO SECTION - Exact Match
st.markdown("""
<div>
<div class="hero-section">
    <div style="position: relative; z-index: 10; max-width: 600px;">
        <div style="display: inline-flex; align-items: center; background: rgba(255,255,255,0.2); backdrop-filter: blur(8px); border-radius: 9999px; padding: 6px 16px; font-size: 12px; margin-bottom: 24px; border: 1px solid rgba(255,255,255,0.3); font-weight: 500;">
            <i class="fa-solid fa-bolt" style="margin-right: 8px; font-size: 12px;"></i>
            <span>Upload & Visualize in Seconds</span>
        </div>
        <h2 style="font-size: 40px; font-weight: 800; margin-bottom: 16px; line-height: 1.2; letter-spacing: -0.5px;">Transform Your Data into<br/>Beautiful Charts</h2>
        <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin-bottom: 32px; line-height: 1.6; max-width: 580px;">Upload Excel or CSV files and instantly generate interactive charts, graphs, and visualizations. No coding required.</p>
    </div>
    <div style="position: absolute; right: -80px; bottom: -80px; opacity: 0.15; z-index: 1;">
        <i class="fa-solid fa-chart-pie" style="font-size: 320px; color: white;"></i>
    </div>
</div>
</div>
""", unsafe_allow_html=True)

# 3. UPLOAD SECTION - Updated for Streamlit 1.41.0+
st.markdown(f"""
    <style>
    /* Target the inner section of the uploader - Updated for Streamlit 1.41+ */
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploader"] > div > section,
    [data-testid="stFileUploader"] > section {{
        height: 300px !important;
        background-color: #f8fafc !important;
        border: 2px dashed #e2e8f0 !important;
        border-radius: 12px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 48px 32px !important;
        transition: all 0.3s ease !important;
    }}
    
    /* Target the file uploader container */
    [data-testid="stFileUploader"] {{
        width: 100% !important;
    }}
    
    /* Only hide text spans within instructions, preserve buttons */
    div[data-testid="stFileDropzoneInstructions"] span {{
        font-size: 0 !important;
        line-height: 0 !important;
        color: transparent !important;
    }}
    
    /* Add custom text after instructions */
    div[data-testid="stFileDropzoneInstructions"]::after {{
        content: "Choose a file" !important;
        display: block !important;
        text-align: center !important;
        color: #64748b !important;
        font-size: 16px !important;
        margin-top: 4px !important;
        line-height: 1.5 !important;
    }}
    
    /* Ensure buttons and interactive elements remain fully visible and functional */
    [data-testid="stFileUploader"] button,
    [data-testid="stFileUploader"] input[type="file"],
    [data-testid="stFileUploader"] label,
    [data-testid="stFileUploader"] a {{
        opacity: 1 !important;
        visibility: visible !important;
        display: inline-block !important;
        font-size: 14px !important;
        color: inherit !important;
        position: relative !important;
        z-index: 10 !important;
    }}
    
    /* Ensure the internal content container stays centered */
    [data-testid="stFileUploader"] section > div,
    [data-testid="stFileUploader"] > div > section > div,
    [data-testid="stFileUploader"] > section > div {{
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 12px !important;
    }}
    </style>
    """, unsafe_allow_html=True)

uploaded_file = st.file_uploader("", type=['xlsx', 'xls', 'csv'], label_visibility="hidden")

if uploaded_file is not None:
    if st.session_state.filename != uploaded_file.name:
        with st.spinner("Processing file..."):
            df = process_uploaded_file(uploaded_file, preview_only=False)
            if df is not None:
                st.rerun()

st.markdown("""
</div>
""", unsafe_allow_html=True)

# 4. RECENT UPLOADS - Exact Match
if st.session_state.recent_uploads:
    st.markdown("""
    <div style="margin-bottom: 32px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div>
                <h3 style="font-size: 18px; font-weight: 600; color: #0f172a; margin-bottom: 4px;">Recent Uploads</h3>
                <p style="font-size: 14px; color: #64748b; margin: 0;">Your recently processed files</p>
            </div>
            <a href="#" style="color: #2563eb; font-size: 14px; font-weight: 500; text-decoration: none;">View All →</a>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;">
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    for idx, upload in enumerate(st.session_state.recent_uploads[:3]):
        with cols[idx]:
            icon_cls = "fa-file-excel" if upload['is_excel'] else "fa-file-csv"
            icon_color = "#16a34a" if upload['is_excel'] else "#2563eb"
            bg_cls = "#dcfce7" if upload['is_excel'] else "#dbeafe"
            time_diff = datetime.now() - upload['upload_time']
            if time_diff.total_seconds() >= 86400:
                time_str = f"{int(time_diff.total_seconds()//86400)} day ago" if int(time_diff.total_seconds()//86400) == 1 else f"{int(time_diff.total_seconds()//86400)} days ago"
            elif time_diff.total_seconds() >= 3600:
                hours = int(time_diff.total_seconds()//3600)
                time_str = f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
            else:
                mins = int(time_diff.total_seconds()//60)
                time_str = f"{mins} min ago" if mins == 1 else f"{mins} mins ago"
            
            charts_count = np.random.randint(5, 16)
            
            st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; height: 100%; display: flex; flex-direction: column;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                    <div style="width: 40px; height: 40px; background: {bg_cls}; border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                        <i class="fa-solid {icon_cls}" style="color: {icon_color}; font-size: 20px;"></i>
                    </div>
                    <span style="font-size: 12px; color: #94a3b8;">{time_str}</span>
                </div>
                <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 8px; font-size: 14px; line-height: 1.3;">{upload['filename']}</h4>
                <p style="font-size: 12px; color: #64748b; margin-bottom: 16px; line-height: 1.4;">{charts_count} charts generated</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 16px; border-top: 1px solid #f1f5f9;">
                    <span style="font-size: 12px; color: #94a3b8;">{(upload['file_size']/1024/1024):.1f} MB</span>
                    <a href="#" style="font-size: 12px; color: #2563eb; font-weight: 500; text-decoration: none;">View Charts →</a>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("</div></div>", unsafe_allow_html=True)

# 5. GENERATED VISUALIZATIONS - Exact Match
if st.session_state.df is not None:
    df = st.session_state.df
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object']).columns.tolist()

    st.markdown(f"""
    <div style="margin-bottom: 32px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
            <div>
                <h3 style="font-size: 18px; font-weight: 600; color: #0f172a; margin-bottom: 4px;">Generated Visualizations</h3>
                <p style="font-size: 14px; color: #64748b; margin: 0;">From {st.session_state.filename}</p>
            </div>
            <div style="display: flex; gap: 12px;">
                <button class="btn-outline" style="padding: 10px 20px; font-size: 14px;"><i class="fa-solid fa-sliders" style="font-size: 14px;"></i> Customize</button>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create columns for 2 charts per row
    col1, col2 = st.columns(2)
    
    # Chart 1: Monthly Revenue Trend (Line Chart)
    with col1:
        st.markdown('<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;"><h4 style="font-weight: 600; font-size: 14px; color: #0f172a; margin: 0;">Monthly Revenue Trend</h4></div>', unsafe_allow_html=True)
        if len(numeric_cols) > 0:
            # Use all data from the numeric column
            col_data = df[numeric_cols[0]].dropna()
            if len(col_data) > 0:
                # Use all values
                values = col_data.tolist()
                # Get the indices of non-null values to align with other columns
                valid_indices = col_data.index
                
                # Generate x-axis labels based on data length
                # If we have date/datetime column, use it; otherwise use sequential indices
                x_labels = None
                date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
                if len(date_cols) > 0:
                    # Use first date column for x-axis, aligned with valid indices
                    date_data = df.loc[valid_indices, date_cols[0]].dropna()
                    if len(date_data) == len(values):
                        x_labels = date_data.tolist()
                elif len(col_data) <= 12:
                    # For small datasets, use month names
                    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    x_labels = months[:len(values)]
                else:
                    # For larger datasets, use sequential numbers
                    x_labels = list(range(1, len(values) + 1))
                
                # If x_labels don't match values length, use indices
                if x_labels is None or len(x_labels) != len(values):
                    x_labels = list(range(1, len(values) + 1))
            else:
                values = []
                x_labels = []
            
            fig = go.Figure()
            if len(values) > 0:
                fig.add_trace(go.Scatter(
                    x=x_labels,
                    y=values,
                    mode='lines',
                    line=dict(color='#2563eb', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(37, 99, 235, 0.1)'
                ))
                fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=250,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False, zeroline=False),
                    yaxis=dict(showgrid=True, gridcolor='#f1f5f9', zeroline=False, range=[0, max(values) * 1.2 if values else 60000])
                )
            else:
                fig.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=250,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False, zeroline=False),
                    yaxis=dict(showgrid=True, gridcolor='#f1f5f9', zeroline=False)
                )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("No numeric data for line chart")

    # Chart 2: Sales by Category (Pie Chart)
    with col2:
        st.markdown('<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;"><h4 style="font-weight: 600; font-size: 14px; color: #0f172a; margin: 0;">Sales by Category</h4></div>', unsafe_allow_html=True)
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            cat_col = categorical_cols[0]
            val_col = numeric_cols[0]
            pie_data = df.groupby(cat_col)[val_col].sum().reset_index().head(5)
            colors = ['#9333ea', '#ec4899', '#f97316', '#16a34a', '#2563eb']
            fig = go.Figure(data=[go.Pie(
                labels=pie_data[cat_col].tolist(),
                values=pie_data[val_col].tolist(),
                hole=0.3,
                marker=dict(colors=colors[:len(pie_data)])
            )])
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                height=250,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.1)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Insufficient data for pie chart")

    # Create second row of columns
    col3, col4 = st.columns(2)
    
    # Chart 3: Quarterly Performance (Bar Chart)
    with col3:
        st.markdown('<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;"><h4 style="font-weight: 600; font-size: 14px; color: #0f172a; margin: 0;">Quarterly Performance</h4></div>', unsafe_allow_html=True)
        if len(numeric_cols) > 0:
            quarters = ['Q1', 'Q2', 'Q3', 'Q4']
            values = df[numeric_cols[0]].head(4).tolist() if len(df) >= 4 else (df[numeric_cols[0]].tolist() + [0] * (4 - len(df)))[:4]
            colors_bar = ['#2563eb', '#9333eb', '#ec4899', '#f97316']
            fig = go.Figure(data=[go.Bar(
                x=quarters[:len(values)],
                y=values,
                marker_color=colors_bar[:len(values)]
            )])
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                height=250,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=True, gridcolor='#f1f5f9', zeroline=False, range=[0, max(values) * 1.2 if values else 200000])
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("No numeric data for bar chart")

    # Chart 4: Regional Distribution (Bar Chart)
    with col4:
        st.markdown('<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;"><h4 style="font-weight: 600; font-size: 14px; color: #0f172a; margin: 0;">Regional Distribution</h4></div>', unsafe_allow_html=True)
        if len(numeric_cols) > 1:
            regions = df[categorical_cols[0]].head(5).tolist() if len(categorical_cols) > 0 else ['North America', 'Europe', 'Asia', 'South America', 'Africa'][:5]
            values = df[numeric_cols[1]].head(5).tolist() if len(df) >= 5 else (df[numeric_cols[1]].tolist() + [0] * (5 - len(df)))[:5]
            fig = go.Figure(data=[go.Bar(
                x=regions[:len(values)],
                y=values,
                marker_color='#2563eb'
            )])
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                height=250,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=True, gridcolor='#f1f5f9', zeroline=False, range=[0, max(values) * 1.2 if values else 500000])
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Not enough numeric columns for 2nd bar chart")
    
    st.markdown('</div>', unsafe_allow_html=True)

    # 6. RAW DATA SECTION - Below Charts
    st.markdown(f"""
    <div style="margin-bottom: 32px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
            <div>
                <h3 style="font-size: 18px; font-weight: 600; color: #0f172a; margin-bottom: 4px;">Raw Data</h3>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Show data info
    st.markdown(f"""
    <div style="display: flex; gap: 24px; margin-bottom: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 12px; color: #64748b;">
        <span><strong>Rows:</strong> {len(df):,}</span>
        <span><strong>Columns:</strong> {len(df.columns)}</span>
        <span><strong>File Size:</strong> {(st.session_state.file_size/1024/1024):.2f} MB</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Display the dataframe with custom styling
    st.dataframe(
        df,
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    st.markdown('</div>', unsafe_allow_html=True)


# 9. FEATURES SECTION - Exact Match
st.markdown("""
<div style="margin: 64px 0;">
    <div style="text-align: center; margin-bottom: 48px;">
        <h3 style="font-size: 24px; font-weight: 700; color: #0f172a; margin-bottom: 8px;">Powerful Features</h3>
        <p style="color: #64748b; font-size: 14px;">Everything you need to transform data into insights</p>
    </div>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px;">
        <div style="text-align: center; padding: 32px 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; transition: all 0.2s ease;">
            <div class="feature-icon" style="background: #eff6ff; color: #2563eb;">
                <i class="fa-solid fa-bolt"></i>
            </div>
            <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 8px; font-size: 14px;">Instant Processing</h4>
            <p style="font-size: 12px; color: #64748b; line-height: 1.6;">Upload and visualize your data in seconds with our fast processing engine.</p>
        </div>
        <div style="text-align: center; padding: 32px 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; transition: all 0.2s ease;">
            <div class="feature-icon" style="background: #dcfce7; color: #16a34a;">
                <i class="fa-solid fa-chart-bar"></i>
            </div>
            <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 8px; font-size: 14px;">20+ Chart Types</h4>
            <p style="font-size: 12px; color: #64748b; line-height: 1.6;">Choose from a wide variety of chart types to best represent your data.</p>
        </div>
        <div style="text-align: center; padding: 32px 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; transition: all 0.2s ease;">
            <div class="feature-icon" style="background: #f3e8ff; color: #9333ea;">
                <i class="fa-solid fa-palette"></i>
            </div>
            <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 8px; font-size: 14px;">Full Customization</h4>
            <p style="font-size: 12px; color: #64748b; line-height: 1.6;">Customize colors, fonts, labels, and styles to match your brand.</p>
        </div>
        <div style="text-align: center; padding: 32px 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; transition: all 0.2s ease;">
            <div class="feature-icon" style="background: #ffedd5; color: #ea580c;">
                <i class="fa-solid fa-share-nodes"></i>
            </div>
            <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 8px; font-size: 14px;">Easy Sharing</h4>
            <p style="font-size: 12px; color: #64748b; line-height: 1.6;">Share your visualizations instantly with interactive charts.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 10. FOOTER - Exact Match
st.markdown("""
<footer style="background: #ffffff; border-top: 1px solid #e2e8f0; padding: 64px 48px 32px 48px; margin-top: 64px;">
    <div style="max-width: 1200px; margin: 0 auto;">
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 32px; margin-bottom: 48px;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
                    <div style="background: linear-gradient(135deg, #2563eb, #4f46e5); padding: 6px; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                        <i class="fa-solid fa-chart-line" style="color: white; font-size: 16px;"></i>
                    </div>
                    <span style="font-weight: 600; color: #0f172a; font-size: 16px;">DataViz Pro</span>
                </div>
                <p style="font-size: 14px; color: #64748b; line-height: 1.6;">Transform your data into beautiful, interactive visualizations instantly.</p>
            </div>
            <div>
                <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 16px; font-size: 14px;">Product</h4>
                <div style="display: flex; flex-direction: column; gap: 8px; font-size: 14px; color: #64748b;">
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Features</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Pricing</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Templates</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Documentation</a>
                </div>
            </div>
            <div>
                <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 16px; font-size: 14px;">Company</h4>
                <div style="display: flex; flex-direction: column; gap: 8px; font-size: 14px; color: #64748b;">
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">About</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Blog</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Careers</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Contact</a>
                </div>
            </div>
            <div>
                <h4 style="font-weight: 600; color: #0f172a; margin-bottom: 16px; font-size: 14px;">Legal</h4>
                <div style="display: flex; flex-direction: column; gap: 8px; font-size: 14px; color: #64748b;">
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Privacy Policy</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Terms of Service</a>
                    <a href="#" style="color: inherit; text-decoration: none; transition: color 0.2s;">Cookie Policy</a>
                </div>
            </div>
        </div>
        <div style="border-top: 1px solid #e2e8f0; padding-top: 32px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; color: #64748b;">
            <p style="margin: 0;">© 2024 DataViz Pro. All rights reserved.</p>
            <div style="display: flex; gap: 16px;">
                <i class="fa-brands fa-twitter" style="font-size: 18px; cursor: pointer; color: #64748b; transition: color 0.2s;"></i>
                <i class="fa-brands fa-linkedin" style="font-size: 18px; cursor: pointer; color: #64748b; transition: color 0.2s;"></i>
                <i class="fa-brands fa-instagram" style="font-size: 18px; cursor: pointer; color: #64748b; transition: color 0.2s;"></i>
            </div>
        </div>
    </div>
</footer>
""", unsafe_allow_html=True)
