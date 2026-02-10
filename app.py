"""
Streamlit Excel Data Visualizer
A web app that reads any Excel file and displays interactive charts.
This app runs entirely inside Docker - no local Python needed!
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="Excel Data Visualizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("📊 Excel Data Visualizer")
st.markdown("Upload any Excel file (.xlsx or .xls) to visualize your data with interactive charts!")

# File uploader in the sidebar
st.sidebar.header("📁 Upload File")
uploaded_file = st.sidebar.file_uploader(
    "Choose an Excel file",
    type=['xlsx', 'xls'],
    help="Upload any Excel file with your data"
)

# Initialize session state for data
if 'df' not in st.session_state:
    st.session_state.df = None
if 'filename' not in st.session_state:
    st.session_state.filename = None

# Process uploaded file
if uploaded_file is not None:
    try:
        # Read the Excel file into a pandas DataFrame
        # This works with any Excel file structure (any columns, any rows)
        df = pd.read_excel(uploaded_file)
        
        # Store in session state (persists across reruns)
        st.session_state.df = df
        st.session_state.filename = uploaded_file.name
        
        st.sidebar.success(f"✅ File loaded: {uploaded_file.name}")
        
    except Exception as e:
        st.sidebar.error(f"❌ Error loading file: {str(e)}")
        st.session_state.df = None
        st.session_state.filename = None

# Clear file button
if st.session_state.df is not None:
    if st.sidebar.button("🗑️ Clear File"):
        st.session_state.df = None
        st.session_state.filename = None
        st.rerun()

# Main content area
if st.session_state.df is None:
    # No file uploaded yet
    st.info("👆 Please upload an Excel file using the sidebar to get started!")
    st.markdown("""
    ### How to use:
    1. Click **"Browse files"** in the sidebar
    2. Select any Excel file (.xlsx or .xls)
    3. The app will automatically load and display your data
    4. Create interactive charts based on your data columns
    """)
else:
    # File is loaded - show data and visualizations
    df = st.session_state.df
    
    # Display file info
    st.success(f"📄 Currently viewing: **{st.session_state.filename}**")
    
    # Data overview
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Rows", len(df))
    with col2:
        st.metric("Total Columns", len(df.columns))
    with col3:
        numeric_cols = df.select_dtypes(include=['number']).columns
        st.metric("Numeric Columns", len(numeric_cols))
    with col4:
        categorical_cols = df.select_dtypes(include=['object']).columns
        st.metric("Text Columns", len(categorical_cols))
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Data Preview", "📊 Bar Chart", "📈 Line Chart", "🥧 Pie Chart"])
    
    with tab1:
        # Data preview
        st.subheader("Data Preview")
        st.dataframe(df, use_container_width=True, height=400)
        
        # Column information
        with st.expander("📝 Column Information"):
            st.write("**Column Names:**", ", ".join(df.columns.tolist()))
            st.write("**Data Types:**")
            st.write(df.dtypes)
            st.write("**Summary Statistics:**")
            st.write(df.describe())
    
    with tab2:
        # Bar Chart
        st.subheader("Bar Chart")
        
        if len(df.columns) < 2:
            st.warning("⚠️ Need at least 2 columns for a bar chart")
        else:
            col_x, col_y = st.columns(2)
            
            with col_x:
                x_column = st.selectbox(
                    "X-axis (Category)",
                    df.columns.tolist(),
                    key="bar_x"
                )
            
            with col_y:
                # Only show numeric columns for Y-axis
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    y_column = st.selectbox(
                        "Y-axis (Value)",
                        numeric_cols,
                        key="bar_y"
                    )
                    
                    # Create bar chart
                    fig = px.bar(
                        df,
                        x=x_column,
                        y=y_column,
                        title=f"{y_column} by {x_column}",
                        labels={x_column: x_column, y_column: y_column}
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("⚠️ No numeric columns found for Y-axis")
    
    with tab3:
        # Line Chart
        st.subheader("Line Chart")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            st.warning("⚠️ No numeric columns found for a line chart")
        else:
            line_column = st.selectbox(
                "Column to plot",
                numeric_cols,
                key="line_col"
            )
            
            # Create line chart
            fig = px.line(
                df,
                y=line_column,
                title=f"{line_column} Over Time",
                labels={'index': 'Index', line_column: line_column}
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        # Pie Chart
        st.subheader("Pie Chart")
        
        if len(df.columns) < 2:
            st.warning("⚠️ Need at least 2 columns for a pie chart")
        else:
            col_cat, col_val = st.columns(2)
            
            with col_cat:
                categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
                if not categorical_cols:
                    # If no categorical columns, allow any column
                    categorical_cols = df.columns.tolist()
                cat_column = st.selectbox(
                    "Category Column",
                    categorical_cols,
                    key="pie_cat"
                )
            
            with col_val:
                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    val_column = st.selectbox(
                        "Value Column",
                        numeric_cols,
                        key="pie_val"
                    )
                    
                    # Group by category and sum values
                    pie_data = df.groupby(cat_column)[val_column].sum().reset_index()
                    
                    # Create pie chart
                    fig = px.pie(
                        pie_data,
                        names=cat_column,
                        values=val_column,
                        title=f"{val_column} Distribution by {cat_column}"
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("⚠️ No numeric columns found for values")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>Built with Streamlit • Works with any Excel file structure</small>
</div>
""", unsafe_allow_html=True)
