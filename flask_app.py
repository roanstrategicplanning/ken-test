"""
Flask Excel Data Visualizer
A web app that reads any Excel file and displays interactive charts.
"""

from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import logging
import pickle
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['DATA_FOLDER'] = '/tmp/flask_data'
app.config['SESSION_PERMANENT'] = False

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)

def save_dataframe(df, session_id):
    """Save DataFrame to disk and return the path"""
    filepath = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.pkl")
    with open(filepath, 'wb') as f:
        pickle.dump(df, f)
    return filepath

def load_dataframe(session_id):
    """Load DataFrame from disk"""
    filepath = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.pkl")
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    return None

def get_session_id():
    """Get or create a session ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    # Get data from session if available
    df = None
    current_filename = None
    has_data = False
    error = None
    
    logger.info('Index route called')
    logger.info(f'Session keys: {list(session.keys())}')
    
    if 'session_id' in session and 'filename' in session:
        logger.info(f'Found session data. Filename: {session.get("filename")}')
        try:
            # Load DataFrame from disk
            logger.info('Attempting to load DataFrame from disk')
            session_id = get_session_id()
            df = load_dataframe(session_id)
            if df is not None:
                logger.info(f'Successfully loaded DataFrame. Shape: {df.shape}, Columns: {list(df.columns)[:5]}')
                current_filename = session['filename']
                has_data = True
            else:
                logger.warning('DataFrame file not found on disk')
                error = 'Data file not found. Please upload again.'
                session.pop('filename', None)
        except Exception as e:
            logger.error(f'Error loading DataFrame from disk: {str(e)}', exc_info=True)
            error = str(e)
            session.pop('filename', None)
    else:
        logger.info('No session data found')
    
    # Get recent uploads from session and format time
    recent_uploads = session.get('recent_uploads', [])
    now = datetime.now()
    for upload in recent_uploads:
        upload_time = datetime.fromisoformat(upload['upload_time'])
        time_diff = now - upload_time
        if time_diff.total_seconds() < 3600:
            upload['time_ago'] = f"{int(time_diff.total_seconds() / 60)} minutes ago"
        elif time_diff.total_seconds() < 86400:
            upload['time_ago'] = f"{int(time_diff.total_seconds() / 3600)} hours ago"
        else:
            upload['time_ago'] = f"{int(time_diff.total_seconds() / 86400)} days ago"
        upload['file_size_mb'] = f"{upload['file_size'] / 1024 / 1024:.1f}"
    
    if has_data and df is not None:
        logger.info(f'Rendering template with data. Rows: {len(df)}, Cols: {len(df.columns)}')
        # Prepare data for template
        columns = df.columns.tolist()
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        logger.info(f'Numeric columns: {len(numeric_cols)}, Categorical columns: {len(categorical_cols)}')
        
        # Convert DataFrame to HTML for display with index for row numbers
        try:
            data_html = df.head(100).to_html(
                classes='min-w-full divide-y divide-gray-200', 
                table_id='data-table', 
                escape=False,
                index=True,
                border=0
            )
            logger.info('Successfully converted DataFrame to HTML')
        except Exception as html_error:
            logger.error(f'Error converting DataFrame to HTML: {str(html_error)}')
            data_html = '<p>Error displaying data table</p>'
        
        return render_template('index.html',
                             has_data=True,
                             current_filename=current_filename,
                             columns=columns,
                             numeric_cols=numeric_cols,
                             categorical_cols=categorical_cols,
                             total_rows=len(df),
                             total_columns=len(columns),
                             numeric_columns=len(numeric_cols),
                             data_html=data_html,
                             recent_uploads=recent_uploads)
    else:
        return render_template('index.html',
                             has_data=False,
                             current_filename=None,
                             error=error,
                             recent_uploads=recent_uploads)

@app.route('/upload', methods=['POST'])
def upload_file():
    logger.info('Upload endpoint called')
    if 'file' not in request.files:
        logger.warning('No file in request')
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    logger.info(f'File received: {file.filename}')
    
    if file.filename == '':
        logger.warning('Empty filename')
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        temp_filepath = None
        try:
            filename = secure_filename(file.filename)
            logger.info(f'Processing file: {filename}')
            
            # Save file temporarily to disk for processing
            temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{uuid.uuid4()}_{filename}")
            file.save(temp_filepath)
            logger.info(f'File saved temporarily to: {temp_filepath}')
            
            # Get file size
            file_size = os.path.getsize(temp_filepath)
            
            # Read file based on extension
            if filename.endswith('.csv'):
                logger.info('Reading CSV file')
                df = pd.read_csv(temp_filepath)
            else:
                logger.info('Reading Excel file')
                # Try reading Excel file with error handling for multiple sheets
                try:
                    # First, try to read the first sheet (default behavior)
                    df = pd.read_excel(temp_filepath, engine='openpyxl')
                    logger.info(f'Successfully read Excel file. Shape: {df.shape}')
                    
                    # Check if we got mostly unnamed columns or empty data, indicating wrong header row
                    unnamed_cols = [col for col in df.columns if 'Unnamed:' in str(col)]
                    if len(unnamed_cols) > len(df.columns) / 2:
                        logger.warning(f'Detected {len(unnamed_cols)} unnamed columns. Trying to find correct header row...')
                        # Try reading without header first to detect the real header
                        df_raw = pd.read_excel(temp_filepath, engine='openpyxl', header=None, nrows=10)
                        
                        # Find the first row with meaningful non-null data
                        header_row = None
                        for idx, row in df_raw.iterrows():
                            non_null_count = row.notna().sum()
                            if non_null_count >= 2:  # At least 2 non-null values
                                # Check if this row looks like headers (contains strings)
                                string_values = [str(v) for v in row if pd.notna(v)]
                                if string_values and any(len(str(v)) > 2 for v in string_values):
                                    header_row = idx
                                    logger.info(f'Found potential header row at index {idx}: {string_values[:5]}')
                                    break
                        
                        if header_row is not None and header_row > 0:
                            logger.info(f'Re-reading with header at row {header_row}')
                            df = pd.read_excel(temp_filepath, engine='openpyxl', header=header_row)
                            logger.info(f'New shape: {df.shape}, Columns: {list(df.columns)[:5]}')
                    
                except Exception as excel_error:
                    logger.warning(f'First Excel read attempt failed: {str(excel_error)}')
                    # If that fails, try reading with different parameters
                    try:
                        # Try reading with header=None in case there's no header row
                        df = pd.read_excel(temp_filepath, engine='openpyxl', header=0)
                        logger.info(f'Successfully read Excel file with header=0. Shape: {df.shape}')
                    except Exception:
                        logger.warning('Second Excel read attempt failed, trying ExcelFile approach')
                        # If still failing, try reading all sheets and concatenate
                        try:
                            excel_file = pd.ExcelFile(temp_filepath, engine='openpyxl')
                            # Read first sheet by default
                            df = pd.read_excel(excel_file, sheet_name=0)
                            logger.info(f'Successfully read Excel file using ExcelFile. Shape: {df.shape}')
                        except Exception as e:
                            logger.error(f'All Excel read attempts failed. Last error: {str(e)}')
                            raise Exception(f"Failed to read Excel file: {str(e)}. Original error: {str(excel_error)}")
            
            # Clean up the DataFrame: drop completely empty columns
            logger.info('Cleaning DataFrame: removing empty columns')
            initial_cols = len(df.columns)
            df = df.dropna(axis=1, how='all')  # Drop columns where all values are NaN
            if len(df.columns) < initial_cols:
                logger.info(f'Removed {initial_cols - len(df.columns)} empty columns')
            
            # Drop completely empty rows
            initial_rows = len(df)
            df = df.dropna(axis=0, how='all')  # Drop rows where all values are NaN
            if len(df) < initial_rows:
                logger.info(f'Removed {initial_rows - len(df)} empty rows')
            
            logger.info(f'Final DataFrame shape: {df.shape}, Columns: {list(df.columns)}')
            
            # Check if DataFrame is empty
            if df.empty:
                return jsonify({'success': False, 'message': 'The Excel file appears to be empty or has no data'}), 400
            
            # Store DataFrame to disk instead of session
            logger.info('Saving DataFrame to disk')
            session_id = get_session_id()
            save_dataframe(df, session_id)
            session['filename'] = filename
            logger.info(f'File processed successfully: {filename}, rows: {len(df)}, cols: {len(df.columns)}')
            
            # Track recent uploads
            if 'recent_uploads' not in session:
                session['recent_uploads'] = []
            
            # Add this upload to recent uploads
            now = datetime.now()
            upload_info = {
                'filename': filename,
                'upload_time': now.isoformat(),
                'upload_timestamp': now.timestamp(),
                'file_size': file_size,
                'row_count': len(df),
                'column_count': len(df.columns),
                'numeric_columns': len(df.select_dtypes(include=['number']).columns),
                'is_excel': filename.endswith('.xlsx') or filename.endswith('.xls')
            }
            
            # Remove if already exists (to avoid duplicates)
            session['recent_uploads'] = [u for u in session['recent_uploads'] if u['filename'] != filename]
            
            # Add to beginning of list
            session['recent_uploads'].insert(0, upload_info)
            
            # Keep only last 10 uploads
            session['recent_uploads'] = session['recent_uploads'][:10]
            
            # Delete the temporary uploaded file after processing
            if temp_filepath and os.path.exists(temp_filepath):
                os.remove(temp_filepath)
                logger.info(f'Temporary file deleted: {temp_filepath}')
            
            return jsonify({'success': True, 'message': 'File uploaded successfully'})
        except Exception as e:
            logger.error(f'Error processing file: {str(e)}', exc_info=True)
            # Clean up temporary file if it exists
            if temp_filepath and os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                    logger.info(f'Temporary file deleted after error: {temp_filepath}')
                except Exception as cleanup_error:
                    logger.error(f'Failed to delete temporary file: {str(cleanup_error)}')
            return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Invalid file type'}), 400

@app.route('/reset', methods=['POST'])
def reset():
    # Delete the DataFrame file from disk
    if 'session_id' in session:
        session_id = session['session_id']
        filepath = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.pkl")
        if os.path.exists(filepath):
            os.remove(filepath)
    session.pop('filename', None)
    return jsonify({'success': True})

@app.route('/debug/session', methods=['GET'])
def debug_session():
    """Debug endpoint to check session contents"""
    debug_info = {
        'session_keys': list(session.keys()),
        'has_session_id': 'session_id' in session,
        'has_filename': 'filename' in session,
        'filename': session.get('filename', None),
        'session_id': session.get('session_id', None),
    }
    
    # Try to load DataFrame if it exists
    if 'session_id' in session:
        try:
            session_id = session['session_id']
            filepath = os.path.join(app.config['DATA_FOLDER'], f"{session_id}.pkl")
            debug_info['file_exists'] = os.path.exists(filepath)
            if os.path.exists(filepath):
                debug_info['file_size'] = os.path.getsize(filepath)
                df = load_dataframe(session_id)
                if df is not None:
                    debug_info['df_shape'] = df.shape
                    debug_info['df_columns'] = df.columns.tolist()[:10]
                    debug_info['df_dtypes'] = {k: str(v) for k, v in df.dtypes.to_dict().items()}
        except Exception as e:
            debug_info['df_loading_error'] = str(e)
    
    return jsonify(debug_info)

@app.route('/chart/bar', methods=['POST'])
def get_bar_chart():
    if 'session_id' not in session:
        return jsonify({'error': 'No data available'}), 400
    
    try:
        data = request.get_json()
        x_col = data.get('x_col')
        y_col = data.get('y_col')
        
        session_id = get_session_id()
        df = load_dataframe(session_id)
        if df is None:
            return jsonify({'error': 'Data not found'}), 400
        
        fig = px.bar(
            df,
            x=x_col,
            y=y_col,
            title=f"{y_col} by {x_col}",
            labels={x_col: x_col, y_col: y_col},
            color_discrete_sequence=['#3B82F6']
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chart/line', methods=['POST'])
def get_line_chart():
    if 'session_id' not in session:
        return jsonify({'error': 'No data available'}), 400
    
    try:
        data = request.get_json()
        line_col = data.get('line_col')
        
        session_id = get_session_id()
        df = load_dataframe(session_id)
        if df is None:
            return jsonify({'error': 'Data not found'}), 400
        
        fig = px.line(
            df,
            y=line_col,
            title=f"{line_col} Over Time",
            labels={'index': 'Index', line_col: line_col},
            color_discrete_sequence=['#3B82F6']
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chart/pie', methods=['POST'])
def get_pie_chart():
    if 'session_id' not in session:
        return jsonify({'error': 'No data available'}), 400
    
    try:
        data = request.get_json()
        cat_col = data.get('cat_col')
        val_col = data.get('val_col')
        
        session_id = get_session_id()
        df = load_dataframe(session_id)
        if df is None:
            return jsonify({'error': 'Data not found'}), 400
        
        # Group by category and sum values
        pie_data = df.groupby(cat_col)[val_col].sum().reset_index()
        
        fig = px.pie(
            pie_data,
            names=cat_col,
            values=val_col,
            title=f"{val_col} Distribution by {cat_col}",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'chart': chart_json})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8501, debug=False)

